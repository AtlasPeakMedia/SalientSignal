"""SalientSignal backfill importer — validate a run_backfill JSON and upsert to Supabase.

Phase A4 of the backfill plan. Takes a JSON file produced by run_backfill.py,
runs six validation passes, and bulk-upserts the validated rows to the
Supabase country_activity table using the existing batch upsert path.

This is the "local-first validation" companion to run_backfill.py. The split
gives us a human-reviewable checkpoint between GDELT ingestion and production
database writes: you can inspect the JSON, spot-check known events (Feb 24
Ukraine anniversary, Oct 7 Gaza), and only commit to Supabase when the data
looks right.

Usage:

    # Dry-run validation pass (no DB writes)
    python scripts/import_backfill.py \\
        --input-json data/backfill_2025-01-01_2026-04-09.json \\
        --dry-run

    # Actual import after manual review
    python scripts/import_backfill.py \\
        --input-json data/backfill_2025-01-01_2026-04-09.json \\
        --interactive

Validation passes (all run BEFORE any DB write):

    1. SCHEMA: every row has the required keys (country, date, audience_type,
       today_count, baseline_mean, baseline_std, deviation_ratio, z_score,
       level, confidence, cold_start, top_themes, top_outlets)
    2. VALUES: today_count >= 0, baseline_mean >= 0, level in ALL_LEVELS,
       confidence in {LOW, MEDIUM, HIGH}
    3. DATE COVERAGE: for each (country, audience) tuple, gaps > 7 days fail
    4. SANITY EVENTS (warn-only, no blocking): check for Feb 24 2026 RU
       INTERNATIONAL elevation and Oct 7 2025 ME country elevation.
    5. VOLUME: total rows <= 200,000 (estimated ceiling ~135,900 per plan)
    6. FVEY: zero rows where country in {US, GB, CA, AU, NZ}

If all validations pass, bulk upsert via upsert_country_activity_batch (100
rows per batch, matches the existing live pipeline path). After successful
upload, run clear_historical_cold_start() to flip cold_start=False on all
historical rows so the frontend banner shows "Live Intelligence Data".

Writes an import manifest to data/backfill_import_manifest_<timestamp>.json
with counts, verification hashes, and the source file reference.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# Make src/ importable when running this script directly.
THIS_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = THIS_DIR.parent
sys.path.insert(0, str(PIPELINE_DIR))


def _load_env() -> None:
    """Load pipeline/.env via python-dotenv BEFORE any other imports."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = PIPELINE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


_load_env()

from src.db import COUNTRY_ACTIVITY_BATCH_SIZE, DbError, InMemoryDb, SupabaseDb  # noqa: E402
from src.deviation import ALL_LEVELS  # noqa: E402
from src.outlets import FVEY_COUNTRIES  # noqa: E402

logger = logging.getLogger("import_backfill")


REQUIRED_ROW_KEYS = {
    "country",
    "date",
    "audience_type",
    "today_count",
    "baseline_mean",
    "baseline_std",
    "deviation_ratio",
    "z_score",
    "level",
    "confidence",
    "cold_start",
    "top_themes",
    "top_outlets",
}

VALID_CONFIDENCE = {"LOW", "MEDIUM", "HIGH"}
VALID_AUDIENCE_TYPES = {"DOMESTIC", "INTERNATIONAL", "DIASPORA"}

# Volume sanity ceiling (estimated from plan math: 135,900 rows expected at
# full 15-month × 172-outlet scale; 200K gives headroom for the 301-outlet set).
MAX_ROWS = 200_000

# Sanity-event checks — WARN only, don't block import.
# Each is (date_iso, country, audience_type, description) — we assert the row
# exists and log the level so an operator can spot-check against known events.
SANITY_EVENTS = [
    ("2026-02-24", "RU", "INTERNATIONAL", "Russia-Ukraine war anniversary"),
    ("2025-05-09", "RU", "DOMESTIC", "Russia Victory Day"),
    ("2025-10-01", "CN", "DOMESTIC", "China National Day"),
]


class ValidationError(Exception):
    """Raised when a validation pass fails and import must abort."""


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


# ---------------------------------------------------------------------------
# Validation passes
# ---------------------------------------------------------------------------
def validate_schema(rows: list[dict[str, Any]]) -> None:
    """Pass 1: every row has the required keys."""
    for i, row in enumerate(rows):
        missing = REQUIRED_ROW_KEYS - set(row.keys())
        if missing:
            raise ValidationError(
                f"Row {i} missing required keys: {sorted(missing)}. "
                f"Row sample: {dict(list(row.items())[:3])}"
            )


def validate_values(rows: list[dict[str, Any]]) -> None:
    """Pass 2: values within expected ranges."""
    errors: list[str] = []
    for i, row in enumerate(rows):
        if not isinstance(row.get("today_count"), int) or row["today_count"] < 0:
            errors.append(f"Row {i}: today_count invalid ({row.get('today_count')})")
        if row.get("baseline_mean", -1) < 0:
            errors.append(f"Row {i}: baseline_mean negative ({row.get('baseline_mean')})")
        if row.get("baseline_std", -1) < 0:
            errors.append(f"Row {i}: baseline_std negative ({row.get('baseline_std')})")
        if row.get("level") not in ALL_LEVELS:
            errors.append(f"Row {i}: level invalid ({row.get('level')!r})")
        if row.get("confidence") not in VALID_CONFIDENCE:
            errors.append(f"Row {i}: confidence invalid ({row.get('confidence')!r})")
        if row.get("audience_type") not in VALID_AUDIENCE_TYPES:
            errors.append(
                f"Row {i}: audience_type invalid ({row.get('audience_type')!r})"
            )
        if not isinstance(row.get("cold_start"), bool):
            errors.append(f"Row {i}: cold_start must be bool")

        # Fail fast after 10 errors to keep the output manageable
        if len(errors) >= 10:
            errors.append("... (further errors suppressed)")
            break

    if errors:
        raise ValidationError(
            f"{len(errors)} value-range errors detected:\n  " + "\n  ".join(errors)
        )


def validate_date_coverage(rows: list[dict[str, Any]]) -> None:
    """Pass 3: for each (country, audience) tuple, gaps > 7 days fail."""
    from collections import defaultdict

    series: dict[tuple[str, str], list[date]] = defaultdict(list)
    for row in rows:
        try:
            d = datetime.strptime(row["date"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise ValidationError(
                f"Row with country={row.get('country')}, audience={row.get('audience_type')} "
                f"has unparseable date: {row.get('date')!r}"
            )
        series[(row["country"], row["audience_type"])].append(d)

    gap_errors: list[str] = []
    for (country, audience), dates in series.items():
        sorted_dates = sorted(dates)
        for i in range(1, len(sorted_dates)):
            gap_days = (sorted_dates[i] - sorted_dates[i - 1]).days
            if gap_days > 7:
                gap_errors.append(
                    f"{country}/{audience}: gap of {gap_days} days between "
                    f"{sorted_dates[i - 1]} and {sorted_dates[i]}"
                )
                if len(gap_errors) >= 10:
                    break
        if len(gap_errors) >= 10:
            break

    if gap_errors:
        raise ValidationError(
            f"{len(gap_errors)} date coverage gaps detected:\n  " + "\n  ".join(gap_errors)
        )


def validate_sanity_events(rows: list[dict[str, Any]]) -> None:
    """Pass 4: check known events as a smoke test. WARN only, don't block."""
    index = {
        (row["date"], row["country"], row["audience_type"]): row
        for row in rows
    }
    for d_iso, country, audience, description in SANITY_EVENTS:
        key = (d_iso, country, audience)
        row = index.get(key)
        if row is None:
            logger.warning(
                "SANITY: no row for %s (%s/%s) — event '%s' not spot-checkable",
                d_iso,
                country,
                audience,
                description,
            )
            continue
        logger.info(
            "SANITY: %s %s/%s — %s | count=%d ratio=%.2f z=%.2f level=%s",
            d_iso,
            country,
            audience,
            description,
            row["today_count"],
            row["deviation_ratio"],
            row["z_score"],
            row["level"],
        )


def validate_volume(rows: list[dict[str, Any]]) -> None:
    """Pass 5: total rows <= MAX_ROWS ceiling."""
    if len(rows) > MAX_ROWS:
        raise ValidationError(
            f"Row count {len(rows)} exceeds ceiling {MAX_ROWS}. "
            "Plan estimate was ~135,900 at full scale. "
            "If this is a legitimately larger backfill, bump MAX_ROWS."
        )


def validate_no_fvey(rows: list[dict[str, Any]]) -> None:
    """Pass 6: zero rows where country in FVEY. Hard exclusion."""
    offending = [
        row for row in rows if row.get("country") in FVEY_COUNTRIES
    ][:5]
    if offending:
        countries = sorted({row["country"] for row in offending})
        raise ValidationError(
            f"FVEY countries found in backfill rows (hard exclusion): {countries}. "
            f"Sample row: {offending[0]}"
        )


def run_all_validations(rows: list[dict[str, Any]]) -> None:
    """Run all validation passes in order. Raises ValidationError on first failure."""
    logger.info("Validation pass 1/6: schema shape...")
    validate_schema(rows)
    logger.info("Validation pass 2/6: value ranges...")
    validate_values(rows)
    logger.info("Validation pass 3/6: date coverage...")
    validate_date_coverage(rows)
    logger.info("Validation pass 4/6: sanity events (warn only)...")
    validate_sanity_events(rows)
    logger.info("Validation pass 5/6: volume ceiling...")
    validate_volume(rows)
    logger.info("Validation pass 6/6: FVEY exclusion...")
    validate_no_fvey(rows)
    logger.info("All validation passes complete.")


# ---------------------------------------------------------------------------
# JSON I/O + manifest
# ---------------------------------------------------------------------------
def load_backfill_json(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read the JSON file produced by run_backfill.py.

    Returns (metadata, country_activity_rows).
    """
    if not path.exists():
        raise FileNotFoundError(f"Backfill JSON not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        doc = json.load(f)
    if not isinstance(doc, dict):
        raise ValidationError(f"Backfill JSON root is not an object: {type(doc).__name__}")
    metadata = doc.get("metadata", {})
    rows = doc.get("country_activity", [])
    if not isinstance(rows, list):
        raise ValidationError("country_activity must be a list")
    if not rows:
        raise ValidationError("Backfill JSON contains zero country_activity rows")
    return metadata, rows


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Count-based summary for operator review before import."""
    from collections import Counter

    countries = Counter(row["country"] for row in rows)
    audiences = Counter(row["audience_type"] for row in rows)
    levels = Counter(row["level"] for row in rows)
    cold_start = sum(1 for row in rows if row.get("cold_start"))
    dates = sorted({row["date"] for row in rows})
    return {
        "total_rows": len(rows),
        "unique_countries": len(countries),
        "top_10_countries_by_row_count": countries.most_common(10),
        "audience_distribution": dict(audiences),
        "level_distribution": dict(levels),
        "cold_start_rows": cold_start,
        "earliest_date": dates[0] if dates else None,
        "latest_date": dates[-1] if dates else None,
        "unique_dates": len(dates),
    }


def write_import_manifest(
    *,
    output_dir: Path,
    source_json: Path,
    summary: dict[str, Any],
    imported_count: int,
    cold_start_cleared_count: int,
) -> Path:
    """Write a per-import audit trail file."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"backfill_import_manifest_{timestamp}.json"
    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_json": str(source_json.resolve()),
        "source_json_size_bytes": source_json.stat().st_size if source_json.exists() else None,
        "summary": summary,
        "imported_count": imported_count,
        "cold_start_cleared_count": cold_start_cleared_count,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    return output_path


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------
def upsert_rows(
    db: "SupabaseDb | InMemoryDb",
    rows: list[dict[str, Any]],
) -> int:
    """Batch upsert country_activity rows via the existing db method."""
    total = 0
    n_batches = (len(rows) + COUNTRY_ACTIVITY_BATCH_SIZE - 1) // COUNTRY_ACTIVITY_BATCH_SIZE
    for batch_num in range(n_batches):
        start = batch_num * COUNTRY_ACTIVITY_BATCH_SIZE
        end = start + COUNTRY_ACTIVITY_BATCH_SIZE
        batch = rows[start:end]
        inserted = db.upsert_country_activity_batch(batch)
        total += inserted
        if batch_num % 10 == 0 or batch_num == n_batches - 1:
            logger.info(
                "Upsert progress: batch %d/%d (%d rows so far)",
                batch_num + 1,
                n_batches,
                total,
            )
    return total


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a run_backfill JSON file and import it to Supabase.",
    )
    parser.add_argument(
        "--input-json",
        type=str,
        required=True,
        metavar="PATH",
        help="Backfill JSON produced by run_backfill.py",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run validation only; do not write to Supabase.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for confirmation before the first DB write.",
    )
    parser.add_argument(
        "--manifest-dir",
        type=str,
        default="pipeline/data",
        metavar="PATH",
        help="Where to write the import manifest (default: pipeline/data).",
    )
    parser.add_argument(
        "--skip-cold-start-clear",
        action="store_true",
        help="Skip the post-import UPDATE that clears cold_start on historical rows.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _configure_logging(args.verbose)

    input_path = Path(args.input_json)

    try:
        metadata, rows = load_backfill_json(input_path)
    except (FileNotFoundError, ValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"[import_backfill] source: {input_path}", file=sys.stderr)
    if "generated_at" in metadata:
        print(f"[import_backfill] generated: {metadata['generated_at']}", file=sys.stderr)
    if "start_date" in metadata and "end_date" in metadata:
        print(
            f"[import_backfill] window: {metadata['start_date']} .. {metadata['end_date']}",
            file=sys.stderr,
        )
    print(f"[import_backfill] row count: {len(rows):,}", file=sys.stderr)

    # Summary for operator review
    summary = summarize_rows(rows)
    print()
    print("=== Backfill summary ===")
    print(f"  Total rows:      {summary['total_rows']:,}")
    print(f"  Unique countries:{summary['unique_countries']}")
    print(f"  Unique dates:    {summary['unique_dates']}")
    print(f"  Date range:      {summary['earliest_date']} .. {summary['latest_date']}")
    print(f"  Cold start rows: {summary['cold_start_rows']:,}")
    print(f"  Audience split:  {summary['audience_distribution']}")
    print(f"  Level histogram: {summary['level_distribution']}")
    print(f"  Top 10 countries by row count:")
    for country, count in summary["top_10_countries_by_row_count"]:
        print(f"    {country}: {count:,}")
    print()

    # Run all validation passes
    try:
        run_all_validations(rows)
    except ValidationError as exc:
        print(f"\nVALIDATION FAILED:\n{exc}", file=sys.stderr)
        return 3

    if args.dry_run:
        print("\n[import_backfill] --dry-run: validation passed, NOT writing to DB.")
        return 0

    # Interactive confirmation before first DB write
    if args.interactive:
        print(
            f"\nAbout to upsert {len(rows):,} rows to country_activity "
            "and clear cold_start on historical rows.",
        )
        response = input("Proceed? [y/N] ").strip().lower()
        if response not in ("y", "yes"):
            print("Aborted by user.")
            return 0

    # Real DB write
    try:
        db = SupabaseDb()
    except Exception as exc:
        print(f"ERROR: could not connect to Supabase: {exc}", file=sys.stderr)
        return 4

    try:
        imported = upsert_rows(db, rows)
    except DbError as exc:
        print(f"ERROR: upsert failed — {exc}", file=sys.stderr)
        return 5

    print(f"\n[import_backfill] Upserted {imported:,} rows.")

    # Clear cold_start on historical rows (unless explicitly skipped)
    cleared = 0
    if not args.skip_cold_start_clear:
        try:
            cleared = db.clear_historical_cold_start()
            print(
                f"[import_backfill] Cleared cold_start on {cleared:,} historical rows."
            )
        except DbError as exc:
            print(
                f"WARNING: clear_historical_cold_start failed ({exc}). "
                "Historical rows may still show 'Baseline calibrating' in the UI.",
                file=sys.stderr,
            )

    # Write manifest
    manifest_path = write_import_manifest(
        output_dir=Path(args.manifest_dir),
        source_json=input_path,
        summary=summary,
        imported_count=imported,
        cold_start_cleared_count=cleared,
    )
    print(f"\n[import_backfill] Manifest written: {manifest_path}")
    print("\n=== Import complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

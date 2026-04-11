"""Validate and upsert a GKG theme backfill JSON to Supabase.

Mirrors pipeline/scripts/import_backfill.py. This script never fetches from
GDELT — it only reads a JSON file produced by run_gkg_backfill.py and writes
to Supabase's country_theme_{monthly|weekly|daily} tables.

The split between run_gkg_backfill.py (local-only) and this import step is
deliberate: the 15-month backfill is a ~4 hour operation and we want to
inspect its output locally before committing to a database write. If the
JSON looks wrong we can re-run the backfill script without touching
Supabase.

Usage:

    # Dry-run validation (no DB writes)
    python -m pipeline.scripts.import_gkg_backfill \\
        --input-json pipeline/data/theme_backfill_monthly.json \\
        --dry-run

    # Interactive import with a [y/N] confirmation before first write
    python -m pipeline.scripts.import_gkg_backfill \\
        --input-json pipeline/data/theme_backfill_monthly.json \\
        --interactive

    # Unattended import (use in Render cron job or CI)
    python -m pipeline.scripts.import_gkg_backfill \\
        --input-json pipeline/data/theme_backfill_monthly.json

Validation passes (all run before any DB write):
    1. Shape: every bucket has the required keys
    2. Value ranges: counts non-negative, share in [0,1], audience enum,
       period_end >= period_start
    3. Volume ceiling: aborts if buckets > 5 million (sanity)
    4. Date freshness: warns if period_start > today (forward-dated bug)
    5. FVEY exclusion: hard reject any US/UK/CA/AU/NZ rows
    6. Period consistency: for monthly, period_start must be day 1 of month;
       for weekly, period_start must be a Monday
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = THIS_DIR.parent
sys.path.insert(0, str(PIPELINE_DIR))

try:
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv(PIPELINE_DIR / ".env")
except ImportError:
    pass

from src.db import DbError, SupabaseDb  # noqa: E402

logger = logging.getLogger("import_gkg_backfill")

# FVEY countries to exclude from any SalientSignal dataset (active-duty OPSEC)
FVEY_COUNTRIES = frozenset({"US", "GB", "UK", "CA", "AU", "NZ"})

VALID_AUDIENCES = frozenset({"DOMESTIC", "INTERNATIONAL", "DIASPORA"})

VALID_PERIOD_TYPES = frozenset({"monthly", "weekly", "daily"})

# Sanity ceiling — reject runs larger than this
MAX_BUCKETS = 5_000_000


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Import a GKG theme backfill JSON to Supabase")
    p.add_argument("--input-json", required=True, help="Path to theme_backfill_*.json")
    p.add_argument(
        "--dry-run", action="store_true",
        help="Validate but don't write to the database",
    )
    p.add_argument(
        "--interactive", action="store_true",
        help="Prompt [y/N] once before the first DB write",
    )
    p.add_argument(
        "--verbose", action="store_true",
        help="Enable DEBUG logging",
    )
    return p.parse_args()


def _load_input(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Input file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path}: {exc}")


def _validate_shape(buckets: list[dict[str, Any]]) -> None:
    """Pass 1: every bucket has the required keys."""
    required = {
        "country", "audience_type", "period_start", "period_end",
        "theme", "article_count", "bucket_total", "share",
    }
    for i, b in enumerate(buckets):
        missing = required - b.keys()
        if missing:
            raise SystemExit(
                f"Bucket {i} missing keys: {sorted(missing)}. Row: {b}"
            )


def _validate_value_ranges(buckets: list[dict[str, Any]]) -> None:
    """Pass 2: counts non-negative, share in [0,1], audience enum, date order."""
    for i, b in enumerate(buckets):
        if b["audience_type"] not in VALID_AUDIENCES:
            raise SystemExit(
                f"Bucket {i}: invalid audience_type {b['audience_type']!r}"
            )
        if b["article_count"] < 0 or b["bucket_total"] < 0:
            raise SystemExit(
                f"Bucket {i}: negative count ({b['article_count']}, {b['bucket_total']})"
            )
        if not 0 <= b["share"] <= 1:
            raise SystemExit(
                f"Bucket {i}: share out of [0,1]: {b['share']}"
            )
        try:
            ps = date.fromisoformat(b["period_start"])
            pe = date.fromisoformat(b["period_end"])
        except (ValueError, TypeError) as exc:
            raise SystemExit(f"Bucket {i}: bad date format: {exc}") from exc
        if pe < ps:
            raise SystemExit(
                f"Bucket {i}: period_end {pe} before period_start {ps}"
            )


def _validate_volume(buckets: list[dict[str, Any]]) -> None:
    """Pass 3: abort on absurd row counts."""
    if len(buckets) > MAX_BUCKETS:
        raise SystemExit(
            f"Bucket count {len(buckets):,} exceeds safety ceiling "
            f"{MAX_BUCKETS:,}. Check the backfill run for bugs."
        )


def _validate_dates(buckets: list[dict[str, Any]]) -> list[str]:
    """Pass 4: warn on forward-dated buckets. Returns a list of warnings."""
    warnings: list[str] = []
    today = datetime.now(timezone.utc).date()
    forward = [
        b for b in buckets
        if date.fromisoformat(b["period_start"]) > today
    ]
    if forward:
        warnings.append(
            f"{len(forward)} buckets have period_start after today {today}"
        )
    return warnings


def _validate_fvey(buckets: list[dict[str, Any]]) -> None:
    """Pass 5: hard reject any FVEY rows."""
    bad = [b for b in buckets if b["country"].upper() in FVEY_COUNTRIES]
    if bad:
        countries = sorted({b["country"] for b in bad})
        raise SystemExit(
            f"FVEY rows leaked into backfill: {len(bad)} rows from {countries}. "
            "The pipeline must exclude US/UK/CA/AU/NZ by hardcoded filter. "
            "Check outlets.json for misclassified entries."
        )


def _validate_period_consistency(
    buckets: list[dict[str, Any]], period_type: str
) -> None:
    """Pass 6: monthly period_starts must be day 1; weekly must be Monday."""
    if period_type == "monthly":
        for i, b in enumerate(buckets):
            ps = date.fromisoformat(b["period_start"])
            if ps.day != 1:
                raise SystemExit(
                    f"Bucket {i}: monthly period_start {ps} is not day 1"
                )
    elif period_type == "weekly":
        for i, b in enumerate(buckets):
            ps = date.fromisoformat(b["period_start"])
            if ps.isoweekday() != 1:
                raise SystemExit(
                    f"Bucket {i}: weekly period_start {ps} is not a Monday"
                )


def _summarize(buckets: list[dict[str, Any]]) -> None:
    if not buckets:
        print("[empty dataset — nothing to summarize]")
        return
    countries = sorted({b["country"] for b in buckets})
    audiences: dict[str, int] = {}
    periods: set[str] = set()
    theme_counts: dict[str, int] = {}
    total_articles = 0
    for b in buckets:
        audiences[b["audience_type"]] = audiences.get(b["audience_type"], 0) + 1
        periods.add(b["period_start"])
        total_articles += b["article_count"]
        theme_counts[b["theme"]] = theme_counts.get(b["theme"], 0) + 1

    top_themes = sorted(theme_counts.items(), key=lambda kv: -kv[1])[:10]

    print()
    print("=== Theme backfill summary ===")
    print(f"  Total bucket rows: {len(buckets):,}")
    print(f"  Unique countries:  {len(countries)}")
    print(f"  Unique periods:    {len(periods)}")
    print(f"  Audience split:    {audiences}")
    print(f"  Sum of article_count across buckets: {total_articles:,}")
    print(f"  Countries: {', '.join(countries[:15])}"
          f"{' ...' if len(countries) > 15 else ''}")
    print("  Top 10 most-referenced themes (by bucket-row count):")
    for theme, n in top_themes:
        print(f"    {theme[:60]:60s} {n:,} buckets")
    print()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    path = Path(args.input_json)
    data = _load_input(path)
    metadata = data.get("metadata", {})
    buckets = data.get("theme_buckets", [])
    period_type = metadata.get("period_type", "monthly")

    print(f"[import_gkg_backfill] source: {path}")
    print(f"[import_gkg_backfill] generated: {metadata.get('generated_at')}")
    print(f"[import_gkg_backfill] window: {metadata.get('start_date')} .. {metadata.get('end_date')}")
    print(f"[import_gkg_backfill] period_type: {period_type}")
    print(f"[import_gkg_backfill] row count: {len(buckets):,}")

    if period_type not in VALID_PERIOD_TYPES:
        raise SystemExit(
            f"metadata.period_type must be one of {sorted(VALID_PERIOD_TYPES)}, "
            f"got {period_type!r}"
        )

    logger.info("Validation pass 1/6: schema shape...")
    _validate_shape(buckets)
    logger.info("Validation pass 2/6: value ranges...")
    _validate_value_ranges(buckets)
    logger.info("Validation pass 3/6: volume ceiling...")
    _validate_volume(buckets)
    logger.info("Validation pass 4/6: date freshness (warn only)...")
    for w in _validate_dates(buckets):
        logger.warning("DATE WARN: %s", w)
    logger.info("Validation pass 5/6: FVEY exclusion...")
    _validate_fvey(buckets)
    logger.info("Validation pass 6/6: period consistency...")
    _validate_period_consistency(buckets, period_type)
    logger.info("All validation passes complete.")

    _summarize(buckets)

    if args.dry_run:
        print("[import_gkg_backfill] --dry-run: validation passed, NOT writing to DB.")
        return 0

    if args.interactive:
        answer = input(
            f"Proceed to upsert {len(buckets):,} rows into "
            f"country_theme_{period_type}? [y/N]: "
        ).strip().lower()
        if answer != "y":
            print("Aborted by user.")
            return 1

    # Write to Supabase
    db = SupabaseDb()
    try:
        count = db.upsert_country_theme_batch(buckets, period_type=period_type)
    except DbError as exc:
        raise SystemExit(f"Upsert failed: {exc}") from exc
    print(f"[import_gkg_backfill] Upserted {count:,} rows.")

    # Write an import manifest alongside the input file for traceability
    manifest_path = path.parent / (
        "theme_import_manifest_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + ".json"
    )
    manifest = {
        "source_json": str(path),
        "source_metadata": metadata,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "rows_upserted": count,
        "target_table": f"country_theme_{period_type}",
    }
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"[import_gkg_backfill] Manifest written: {manifest_path}")
    print()
    print("=== Import complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

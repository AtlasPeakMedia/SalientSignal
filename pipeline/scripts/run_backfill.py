"""SalientSignal historical backfill — local CLI entry point.

Phase A3 of the backfill plan. Queries GDELT TimelineVolRaw for every outlet
in ``outlets.json`` over the specified date range, aggregates into per-
(country, date, audience_type) daily counts, computes 30-day rolling
baselines, and writes the full ``country_activity`` row set to a JSON file.

This script NEVER touches Supabase. It's the "local-first validation"
half of the backfill workflow. The companion ``import_backfill.py`` script
(A4) validates the JSON and upserts to Supabase in a separate step.

Usage examples:

    # Full 15-month backfill from Jan 1, 2025 to April 9, 2026
    python scripts/run_backfill.py \\
        --start-date 2025-01-01 \\
        --end-date 2026-04-09 \\
        --output-json data/backfill_2025-01-01_2026-04-09.json

    # Resume a crashed run from a specific outlet alphabetically
    python scripts/run_backfill.py \\
        --start-date 2025-01-01 \\
        --end-date 2026-04-09 \\
        --output-json data/backfill_resume.json \\
        --resume-from xinhuanet.com \\
        --force

    # Smoke test: 30 days, verbose
    python scripts/run_backfill.py \\
        --start-date 2025-01-01 \\
        --end-date 2025-01-30 \\
        --output-json data/backfill_smoke.json \\
        --verbose

Safety behaviors:
  - Refuses to overwrite an existing --output-json file unless --force is set
  - SIGINT / Ctrl-C writes a partial JSON marked metadata.interrupted=true
    so you can inspect progress or resume
  - Never contacts Supabase — validation + upsert is a separate script (A4)
  - Aborts if start_date > end_date

Phase A3 does NOT run preflight Supabase checks because it writes to JSON
only. Credentials are checked by A4 at import time.
"""
from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# Make src/ importable when running this script directly.
THIS_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = THIS_DIR.parent
sys.path.insert(0, str(PIPELINE_DIR))


def _load_env() -> None:
    """Load pipeline/.env via python-dotenv BEFORE any other imports.

    Phase A3 doesn't strictly need Supabase credentials, but we load .env
    anyway so the logging / rate limit overrides can come from environment
    variables if desired. Mirrors the run_pipeline.py pattern.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = PIPELINE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


_load_env()

# Imports AFTER env is loaded
from src.backfill import BackfillResult, run_backfill  # noqa: E402
from src.gdelt_timeline_client import (  # noqa: E402
    DEFAULT_TIMELINE_RATE_LIMIT_SECONDS,
    query_domain_timeline,
)
from src.outlets import get_all_outlets  # noqa: E402

logger = logging.getLogger("run_backfill")


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SalientSignal historical backfill (writes to JSON, never touches Supabase).",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        metavar="YYYY-MM-DD",
        help="Inclusive first day of the backfill window.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        required=True,
        metavar="YYYY-MM-DD",
        help="Inclusive last day of the backfill window.",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        required=True,
        metavar="PATH",
        help="Write BackfillResult to this JSON file. Refuses to overwrite unless --force.",
    )
    parser.add_argument(
        "--outlets-file",
        type=str,
        default=None,
        metavar="PATH",
        help="Alternative outlets.json path (default: pipeline/data/outlets.json).",
    )
    parser.add_argument(
        "--resume-from",
        type=str,
        default=None,
        metavar="DOMAIN",
        help="Skip outlets alphabetically strictly BEFORE this domain (resume a crashed run).",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=DEFAULT_TIMELINE_RATE_LIMIT_SECONDS,
        metavar="SECONDS",
        help=(
            f"Seconds to sleep between GDELT queries "
            f"(default: {DEFAULT_TIMELINE_RATE_LIMIT_SECONDS}). "
            "Lower at your own risk — GDELT throttles aggressively."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing --output-json file.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log every outlet query result (default: every 10th).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load outlets + validate arguments but do not contact GDELT.",
    )
    return parser.parse_args(argv)


def _parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date {s!r}: expected YYYY-MM-DD"
        ) from exc


def _build_result_dict(
    *,
    result: BackfillResult,
    start_date: date,
    end_date: date,
    outlet_count: int,
    elapsed_seconds: float,
    interrupted: bool = False,
    include_raw_counts: bool = True,
) -> dict[str, Any]:
    """Serialize a BackfillResult (or partial result) to a JSON-ready dict."""
    metadata: dict[str, Any] = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "outlet_count": outlet_count,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "stats": result.stats.to_dict(),
    }
    if interrupted:
        metadata["interrupted"] = True

    doc: dict[str, Any] = {
        "metadata": metadata,
        "country_activity": result.country_activity,
        "failures": [[domain, err] for domain, err in result.failures],
    }

    if include_raw_counts:
        # (domain, date) -> count is a dict-of-tuples — flatten for JSON.
        # Use ISO date strings so the JSON is human-inspectable.
        doc["raw_outlet_daily_counts"] = [
            {"domain": domain, "date": d.isoformat(), "volume": count}
            for (domain, d), count in sorted(result.raw_outlet_daily_counts.items())
        ]
    return doc


def _write_result_json(
    output_path: Path,
    doc: dict[str, Any],
    force: bool,
) -> None:
    if output_path.exists() and not force:
        raise FileExistsError(
            f"{output_path} already exists. Pass --force to overwrite."
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False, default=str)


class _InterruptHandler:
    """Catch SIGINT so we can write a partial JSON before exiting."""

    def __init__(self) -> None:
        self.interrupted = False
        self._original = signal.getsignal(signal.SIGINT)

    def __enter__(self) -> "_InterruptHandler":
        signal.signal(signal.SIGINT, self._handle)
        return self

    def __exit__(self, *_args) -> None:
        signal.signal(signal.SIGINT, self._original)

    def _handle(self, _signum, _frame) -> None:
        if self.interrupted:
            # Second Ctrl-C: propagate normally so we don't block
            signal.signal(signal.SIGINT, self._original)
            raise KeyboardInterrupt
        self.interrupted = True
        print(
            "\n[run_backfill] SIGINT received — finishing current outlet then writing partial JSON...",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _configure_logging(args.verbose)

    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)
    if start_date > end_date:
        print(
            f"ERROR: --start-date {start_date} must be <= --end-date {end_date}",
            file=sys.stderr,
        )
        return 2

    output_path = Path(args.output_json)
    if output_path.exists() and not args.force:
        print(
            f"ERROR: {output_path} already exists. Pass --force to overwrite.",
            file=sys.stderr,
        )
        return 3

    outlets_path = Path(args.outlets_file) if args.outlets_file else None
    if outlets_path is not None:
        from src.outlets import load_outlets

        outlets = list(load_outlets(outlets_path).values())
    else:
        outlets = get_all_outlets()

    print(
        f"[run_backfill] start={start_date} end={end_date} "
        f"outlets={len(outlets)} rate_limit={args.rate_limit}s "
        f"output={output_path}",
        file=sys.stderr,
    )
    if args.resume_from:
        print(f"[run_backfill] resume_from={args.resume_from}", file=sys.stderr)

    if args.dry_run:
        print(
            "[run_backfill] DRY RUN — would query GDELT but skipping network.",
            file=sys.stderr,
        )
        return 0

    # Build the actual timeline client with the requested rate limit.
    def timeline_client(
        domain: str,
        *,
        start_date: date,
        end_date: date,
    ):
        return query_domain_timeline(
            domain,
            start_date=start_date,
            end_date=end_date,
            rate_limit_seconds=args.rate_limit,
        )

    started = time.monotonic()
    try:
        with _InterruptHandler() as interrupt:
            result = run_backfill(
                start_date=start_date,
                end_date=end_date,
                outlets=outlets,
                timeline_client=timeline_client,
                resume_from=args.resume_from,
                verbose=args.verbose,
            )
    except KeyboardInterrupt:
        print(
            "[run_backfill] Second SIGINT — aborting without partial JSON",
            file=sys.stderr,
        )
        return 130

    elapsed = time.monotonic() - started
    doc = _build_result_dict(
        result=result,
        start_date=start_date,
        end_date=end_date,
        outlet_count=len(outlets),
        elapsed_seconds=elapsed,
        interrupted=interrupt.interrupted,
    )

    try:
        _write_result_json(output_path, doc, force=args.force)
    except FileExistsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    print()
    print("=== Backfill complete ===")
    stats = result.stats.to_dict()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"  elapsed_seconds: {elapsed:.2f}")
    print(f"  output: {output_path}")

    if result.failures:
        print(f"\n{len(result.failures)} outlet failures (see JSON for details):")
        for domain, err in result.failures[:5]:
            print(f"  {domain}: {err}")
        if len(result.failures) > 5:
            print(f"  ... and {len(result.failures) - 5} more")

    if interrupt.interrupted:
        print(
            "\nWARNING: run was interrupted. JSON file is marked metadata.interrupted=true.",
            file=sys.stderr,
        )
        return 130

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

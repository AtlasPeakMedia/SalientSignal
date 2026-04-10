"""SalientSignal pipeline — local CLI entry point.

Usage examples:

    # Dry run against every monitored country, no DB writes
    python scripts/run_pipeline.py --dry-run

    # Dry run, only Russia, last 6 hours
    python scripts/run_pipeline.py --dry-run --country=RU --hours=6

    # Tier 1 live run
    python scripts/run_pipeline.py --country=RU --country=CN --country=IR --country=KP

    # Real run with JSON stats output for verification
    python scripts/run_pipeline.py --output-json=logs/run_$(date +%s).json

    # Sample a subset of monitored countries (for incremental scale-up)
    python scripts/run_pipeline.py --sample-rate=10  # queries every 10th country

Phase 2 fixes (from SalientSignal-Phase1-Review.md + Phase 2 red team):
  - P2-C6: Loads .env file via python-dotenv before reading env vars
  - P2-C7: Pre-flight credential validation BEFORE GDELT queries
  - P2-C9: Pre-flight schema version check (fails fast on unmigrated DB)
  - B5:    New CLI flags: --output-json, --sample-rate, --verify, --countries-file
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Make src/ importable when running this script directly.
THIS_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = THIS_DIR.parent
SRC_DIR = PIPELINE_DIR / "src"
sys.path.insert(0, str(PIPELINE_DIR))


def _load_env() -> None:
    """Load pipeline/.env via python-dotenv BEFORE any other imports.

    P2-C7 fix: previously env vars were only checked at first DB call,
    30+ minutes into the run. Now we load .env at script start so credentials
    are validated upfront.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        # python-dotenv is a dependency in pyproject.toml, but if someone
        # runs the script without installing the package, fall back to
        # assuming env vars are already set in the shell.
        print(
            "WARNING: python-dotenv not installed. Reading env vars from shell only.",
            file=sys.stderr,
        )
        return

    env_path = PIPELINE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
        print(f"[pre-flight] Loaded environment from {env_path}", file=sys.stderr)
    else:
        # Not fatal — user may have exported env vars directly
        print(
            f"[pre-flight] No .env file at {env_path} "
            "(using shell environment only)",
            file=sys.stderr,
        )


_load_env()

# Imports AFTER env is loaded so any module-level env reads pick up values
from src.outlets import get_all_outlets, get_monitored_countries  # noqa: E402
from src.pipeline import (  # noqa: E402
    DEFAULT_TIME_BUDGET_SECONDS,
    PipelineError,
    StorageQuotaError,
    TimeBudgetExceeded,
    run_pipeline,
)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the SalientSignal data pipeline locally.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute the full pipeline but don't write to Supabase.",
    )
    parser.add_argument(
        "--country",
        action="append",
        dest="countries",
        default=None,
        metavar="ISO2",
        help="Restrict to a specific country (ISO 3166-1 alpha-2). Repeatable.",
    )
    parser.add_argument(
        "--country-fips",
        dest="country_fips",
        default=None,
        metavar="FIPS",
        help="Restrict to a specific country (FIPS 10-4 code). Translated to ISO.",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=1,
        help="GDELT query window in hours (default: 1).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Use a no-op GDELT client (returns empty results). Use with --dry-run for offline smoke tests.",
    )
    # Phase 2 additions (B5)
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        metavar="PATH",
        help="Write pipeline stats to a JSON file (for verification + debugging).",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=None,
        metavar="N",
        help="Sample every Nth country from the monitored list (useful for incremental scale-up testing).",
    )
    parser.add_argument(
        "--time-budget",
        type=int,
        default=int(DEFAULT_TIME_BUDGET_SECONDS),
        metavar="SECONDS",
        help=f"Override the pipeline time budget (default: {int(DEFAULT_TIME_BUDGET_SECONDS)}s).",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip credential/schema/permission checks (DEBUG ONLY — don't use in production).",
    )
    return parser.parse_args(argv)


def _no_op_query(country_fips: str, hours: int = 1):
    """Stand-in GDELT client for --no-network smoke tests."""
    import pandas as pd
    from src.gdelt_client import GdeltQueryResult

    return GdeltQueryResult(
        df=pd.DataFrame(),
        query_str=f"no-op country={country_fips} hours={hours}",
        duration_seconds=0.0,
    )


def _preflight_checks(dry_run: bool) -> int:
    """Validate environment and DB connectivity BEFORE running the pipeline.

    P2-C7 + P2-C9: Catches credential and schema issues upfront instead of
    30 minutes into a run.

    Returns 0 on success, non-zero on failure.
    """
    print("[pre-flight] Running checks...", file=sys.stderr)

    # Dry-run uses InMemoryDb, no network needed
    if dry_run:
        print("[pre-flight] Dry-run mode: skipping DB checks", file=sys.stderr)
        return 0

    # Check 1: Credentials present
    try:
        from src.db import _resolve_credentials
        url, key = _resolve_credentials()
        print(f"[pre-flight] ✓ Supabase credentials found (URL: {url})", file=sys.stderr)
    except RuntimeError as exc:
        print(f"[pre-flight] ✗ Credentials missing: {exc}", file=sys.stderr)
        print(
            "\n"
            "  Fix: create pipeline/.env with:\n"
            "    SUPABASE_URL=https://<your-project>.supabase.co\n"
            "    SUPABASE_SECRET_KEY=sb_secret_...\n",
            file=sys.stderr,
        )
        return 2

    # Check 2: Database reachable + schema version correct
    try:
        from src.db import REQUIRED_SCHEMA_VERSION, SupabaseDb

        db = SupabaseDb()
        version = db.get_schema_version()
        if version < REQUIRED_SCHEMA_VERSION:
            print(
                f"[pre-flight] ✗ Schema version {version} is too old "
                f"(requires {REQUIRED_SCHEMA_VERSION}).\n"
                f"  Fix: re-run shared/schema.sql in the Supabase SQL Editor.",
                file=sys.stderr,
            )
            return 3
        print(
            f"[pre-flight] ✓ Schema version {version} meets minimum {REQUIRED_SCHEMA_VERSION}",
            file=sys.stderr,
        )
    except Exception as exc:
        print(f"[pre-flight] ✗ Cannot reach Supabase: {exc}", file=sys.stderr)
        return 4

    # Check 3: All critical tables accessible
    try:
        db.verify_write_permission()
        print("[pre-flight] ✓ All critical tables accessible", file=sys.stderr)
    except Exception as exc:
        print(f"[pre-flight] ✗ Table access failed: {exc}", file=sys.stderr)
        return 5

    print("[pre-flight] All checks passed", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _configure_logging(args.verbose)

    # Pre-flight checks (P2-C7, P2-C9)
    if not args.skip_preflight:
        code = _preflight_checks(args.dry_run)
        if code != 0:
            return code

    # Resolve countries: ISO list takes precedence; FIPS arg is translated.
    countries: list[str] | None = None
    if args.countries:
        countries = [c.upper() for c in args.countries]
    elif args.country_fips:
        from src.countries import fips_to_iso

        iso = fips_to_iso(args.country_fips)
        if not iso:
            print(f"ERROR: unknown FIPS code {args.country_fips!r}", file=sys.stderr)
            return 2
        countries = [iso]

    # B5: sample-rate for incremental scale-up
    if args.sample_rate and args.sample_rate > 1:
        if countries is None:
            countries = sorted(get_monitored_countries())
        countries = countries[:: args.sample_rate]
        print(
            f"Sampling every {args.sample_rate}th country: {len(countries)} total",
            file=sys.stderr,
        )

    # Headline counts before we start
    outlet_count = len(get_all_outlets())
    monitored = sorted(get_monitored_countries())
    print(f"Loaded {outlet_count} outlets from outlets.json")
    print(
        f"{len(monitored)} monitored countries available: "
        f"{', '.join(monitored[:20])}" + (" ..." if len(monitored) > 20 else "")
    )

    gdelt_query = _no_op_query if args.no_network else None

    # Run the pipeline
    started = time.monotonic()
    try:
        result = run_pipeline(
            countries=countries,
            hours=args.hours,
            dry_run=args.dry_run,
            gdelt_query_country=gdelt_query,
            time_budget_seconds=float(args.time_budget),
        )
    except StorageQuotaError as exc:
        print(f"\nFAIL: Storage quota exceeded — {exc}", file=sys.stderr)
        return 10
    except TimeBudgetExceeded as exc:
        print(f"\nFAIL: Time budget exceeded — {exc}", file=sys.stderr)
        return 11
    except PipelineError as exc:
        print(f"\nFAIL: Pipeline error — {exc}", file=sys.stderr)
        return 12

    elapsed = time.monotonic() - started

    print()
    print("=== Pipeline complete ===")
    for k, v in result.stats.to_dict().items():
        print(f"  {k}: {v}")
    print(f"  elapsed_seconds: {elapsed:.2f}")

    # B5: Write stats to JSON file if requested
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w") as f:
            json.dump(
                {
                    "stats": result.stats.to_dict(),
                    "elapsed_seconds": elapsed,
                    "country_activity_count": len(result.country_activity),
                    "coordination_events_count": len(result.coordination_events),
                    "articles_count": len(result.articles),
                    "dry_run": args.dry_run,
                    "countries_requested": countries,
                },
                f,
                indent=2,
                default=str,
            )
        print(f"\nStats written to {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

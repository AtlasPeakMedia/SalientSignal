"""SalientSignal pipeline — local CLI entry point.

Usage examples:

    # Dry run against every monitored country, no DB writes
    python scripts/run_pipeline.py --dry-run

    # Dry run, only Russia, last 6 hours
    python scripts/run_pipeline.py --dry-run --country=RU --hours=6

    # Real run (requires SUPABASE_URL + SUPABASE_SECRET_KEY env vars)
    python scripts/run_pipeline.py --hours=1
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Make src/ importable when running this script directly.
THIS_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = THIS_DIR.parent
SRC_DIR = PIPELINE_DIR / "src"
sys.path.insert(0, str(PIPELINE_DIR))

from src.outlets import get_all_outlets, get_monitored_countries  # noqa: E402
from src.pipeline import run_pipeline  # noqa: E402


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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _configure_logging(args.verbose)

    # Resolve countries: ISO list takes precedence; FIPS arg is translated.
    countries: list[str] | None = None
    if args.countries:
        countries = [c.upper() for c in args.countries]
    elif args.country_fips:
        from src.countries import fips_to_iso

        iso = fips_to_iso(args.country_fips)
        if not iso:
            print(f"ERROR: unknown FIPS code {args.country_fips!r}")
            return 2
        countries = [iso]

    # Headline counts before we start
    outlet_count = len(get_all_outlets())
    monitored = sorted(get_monitored_countries())
    print(f"Loaded {outlet_count} outlets from outlets.json")
    print(
        f"{len(monitored)} monitored countries available: "
        f"{', '.join(monitored[:20])}" + (" ..." if len(monitored) > 20 else "")
    )

    gdelt_query = _no_op_query if args.no_network else None

    result = run_pipeline(
        countries=countries,
        hours=args.hours,
        dry_run=args.dry_run,
        gdelt_query_country=gdelt_query,
    )

    print()
    print("=== Pipeline complete ===")
    for k, v in result.stats.to_dict().items():
        print(f"  {k}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

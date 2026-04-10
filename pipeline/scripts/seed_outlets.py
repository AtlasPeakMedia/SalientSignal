"""Seed the outlet_classification table from outlets.json.

Run once after applying shared/schema.sql, and any time you add new outlets
to pipeline/data/outlets.json. The script reads outlets.json, normalizes the
records into Supabase row shapes, and upserts them into outlet_classification.

Usage:

    # Real run (requires SUPABASE_URL + SUPABASE_SECRET_KEY env vars)
    python scripts/seed_outlets.py

    # Dry run — print rows but don't write
    python scripts/seed_outlets.py --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = THIS_DIR.parent
sys.path.insert(0, str(PIPELINE_DIR))

from src.db import make_db  # noqa: E402
from src.outlets import get_all_outlets  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the outlet_classification Supabase table from outlets.json.",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print rows but don't write to Supabase.")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable DEBUG logging.")
    return parser.parse_args(argv)


def _to_db_row(outlet) -> dict:
    """Convert an OutletRecord into the schema row shape."""
    return {
        "domain": outlet.domain,
        "country": outlet.country,
        "audience_type": outlet.audience_type,
        "outlet_name": outlet.outlet_name,
        "outlet_type": outlet.outlet_type or None,
        "languages": list(outlet.languages),
        "is_state_owned": outlet.is_state_owned,
        "is_state_aligned": outlet.is_state_aligned,
        "confidence": outlet.confidence,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    outlets = get_all_outlets()
    rows = [_to_db_row(o) for o in outlets]
    print(f"Loaded {len(rows)} outlets from outlets.json")

    if args.dry_run:
        print("DRY RUN: would upsert the following outlets (first 5):")
        for r in rows[:5]:
            print(f"  - {r['domain']:35s}  {r['country']}  {r['audience_type']}  {r['outlet_name']}")
        if len(rows) > 5:
            print(f"  ... and {len(rows) - 5} more")
        return 0

    db = make_db(dry_run=False)
    inserted = db.upsert_outlets(rows)
    print(f"Upserted {inserted} outlets into outlet_classification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

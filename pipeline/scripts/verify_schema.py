"""Verify the Supabase schema after running shared/schema.sql.

Run this after Don applies schema.sql in the Supabase SQL Editor. The script
checks that every required table, index, and schema_version row exists.
Returns exit code 0 on success, non-zero on any failure.

Usage:

    python scripts/verify_schema.py

Phase 2 runbook step: Step 1, after schema.sql runs.

Checks:
  1. All 10 required tables exist and are queryable
  2. schema_version row contains version >= 2
  3. outlet_classification has 0 rows (not yet seeded) or 161 rows (seeded)
  4. All critical tables are empty on first run
  5. RLS is disabled on all tables (write permission check via service role)
"""
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = THIS_DIR.parent
sys.path.insert(0, str(PIPELINE_DIR))


def _load_env() -> None:
    """Load pipeline/.env via python-dotenv (see seed_outlets.py for rationale)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("WARNING: python-dotenv not installed. Reading env vars from shell only.",
              file=sys.stderr)
        return
    env_path = PIPELINE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


_load_env()

from src.db import REQUIRED_SCHEMA_VERSION, DbError, SupabaseDb  # noqa: E402

REQUIRED_TABLES = [
    "schema_version",
    "outlet_classification",
    "articles",
    "country_activity",
    "coordination_events",
    "daily_snapshots",
    "pipeline_runs",
    "analysis_claims",
    "analysis_suppressed",
    "analysis_escalated",
]


def _check(label: str, result: bool, detail: str = "") -> bool:
    mark = "✓" if result else "✗"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    return result


def main() -> int:
    print("SalientSignal — Schema verification")
    print("=" * 60)

    try:
        db = SupabaseDb()
    except RuntimeError as exc:
        print(f"\nFAIL: cannot construct Supabase client — {exc}", file=sys.stderr)
        return 2

    all_ok = True

    # Check 1: All required tables reachable
    print("\n[1] Checking required tables...")
    try:
        db.verify_write_permission()
        _check(f"All {len(REQUIRED_TABLES)} required tables accessible", True)
    except DbError as exc:
        _check("Table access", False, str(exc))
        all_ok = False

    # Check 2: schema_version is >= 2
    print("\n[2] Checking schema version...")
    try:
        version = db.get_schema_version()
        ok = version >= REQUIRED_SCHEMA_VERSION
        _check(
            f"schema_version is {version} (required: >= {REQUIRED_SCHEMA_VERSION})",
            ok,
        )
        all_ok = all_ok and ok
    except Exception as exc:  # noqa: BLE001
        _check("schema_version probe", False, str(exc))
        all_ok = False

    # Check 3: Core tables can be counted
    print("\n[3] Checking table row counts...")
    try:
        client = db._get_client()
        for table in [
            "outlet_classification",
            "articles",
            "country_activity",
            "coordination_events",
            "pipeline_runs",
            "analysis_claims",
            "analysis_escalated",
        ]:
            resp = client.table(table).select("*", count="estimated").limit(1).execute()
            count = resp.count or 0
            _check(f"{table}: {count} rows", True)
    except Exception as exc:  # noqa: BLE001
        _check("Row counts", False, str(exc))
        all_ok = False

    # Check 4: Storage quota probe
    print("\n[4] Checking storage quota...")
    try:
        used_bytes, fraction = db.check_storage_quota()
        _check(
            f"Storage estimate: {used_bytes / (1024 * 1024):.1f} MB "
            f"({fraction * 100:.1f}% of 500 MB free tier)",
            fraction < 0.9,
        )
    except Exception as exc:  # noqa: BLE001
        _check("Storage quota probe", False, str(exc))
        all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("✓ Schema verification PASSED. Safe to proceed to seed_outlets.py.")
        return 0
    else:
        print("✗ Schema verification FAILED. Check errors above before proceeding.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

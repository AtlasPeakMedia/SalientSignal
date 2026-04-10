"""SalientSignal pipeline pre-flight check.

Phase E17 of the backfill plan. Runs a handful of smoke tests against the
current environment to catch deployment configuration problems BEFORE the
pipeline tries to do real work. Call this before clicking "Deploy" in
Render, after setting env vars, or any time you're debugging a run that
won't start.

Checks, in order:

    1. Python version >= 3.11
    2. Required pipeline modules import cleanly (no syntax errors, no
       missing dependencies, no version skew between gdeltdoc/pandas/etc.)
    3. outlets.json loads without error, has >= 300 entries, covers at
       least 80 countries, no FVEY contamination
    4. Environment variables are present and non-empty:
       - SUPABASE_URL
       - SUPABASE_SECRET_KEY (or a fallback key name)
    5. Supabase credentials actually work: can connect, can read
       schema_version, version matches REQUIRED_SCHEMA_VERSION
    6. All critical tables are accessible (SELECT probe)
    7. Schema version check: get_schema_version() >= REQUIRED_SCHEMA_VERSION
    8. GDELT DOC 2.0 endpoint is reachable: issue ONE test query to
       confirm the library works end-to-end
    9. Print a summary + exit code (0 = green, non-zero = first failing check)

Usage:

    python scripts/preflight_check.py

    # Skip the GDELT probe (faster, no network requirement)
    python scripts/preflight_check.py --skip-gdelt

    # Offline-only mode: skip everything that needs Supabase or GDELT
    python scripts/preflight_check.py --offline

Exit codes:
    0  - all checks passed
    1  - import / Python version / outlets.json problem
    2  - environment variables missing
    3  - Supabase credentials invalid or unreachable
    4  - schema version too old
    5  - table access denied
    6  - GDELT probe failed
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = THIS_DIR.parent
sys.path.insert(0, str(PIPELINE_DIR))


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = PIPELINE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


_load_env()


# Friendly output helpers
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"
BOLD = "\033[1m"


def _ok(msg: str) -> None:
    print(f"  {GREEN}[✓]{RESET} {msg}")


def _fail(msg: str) -> None:
    print(f"  {RED}[✗]{RESET} {msg}")


def _warn(msg: str) -> None:
    print(f"  {YELLOW}[!]{RESET} {msg}")


def _header(msg: str) -> None:
    print(f"\n{BOLD}{msg}{RESET}")


# --- Individual checks ---

def check_python_version() -> int:
    _header("[1] Python version")
    if sys.version_info < (3, 11):
        _fail(f"Python {sys.version.split()[0]} is too old (need >= 3.11)")
        return 1
    _ok(f"Python {sys.version.split()[0]}")
    return 0


def check_imports() -> int:
    _header("[2] Core module imports")
    try:
        from src import (  # noqa: F401
            antihal,
            backfill,
            baselines,
            classifier,
            coordination,
            countries,
            db,
            deviation,
            gdelt_client,
            gdelt_timeline_client,
            outlets,
            pipeline,
            themes,
        )
        _ok("All pipeline modules import cleanly")
        return 0
    except Exception as exc:
        _fail(f"Import failed: {exc}")
        return 1


def check_outlets() -> int:
    _header("[3] Outlet database (outlets.json)")
    try:
        from src.outlets import (
            FVEY_COUNTRIES,
            get_all_outlets,
            get_monitored_countries,
        )

        outlets = get_all_outlets()
        if len(outlets) < 300:
            _fail(
                f"Only {len(outlets)} outlets loaded (expected >= 300 after B8)"
            )
            return 1
        _ok(f"{len(outlets)} outlets loaded")

        countries = get_monitored_countries()
        if len(countries) < 80:
            _fail(f"Only {len(countries)} countries covered (expected >= 80)")
            return 1
        _ok(f"{len(countries)} countries covered")

        fvey = [o for o in outlets if o.country in FVEY_COUNTRIES]
        if fvey:
            _fail(f"FVEY contamination: {[o.domain for o in fvey]}")
            return 1
        _ok("FVEY exclusion intact")
        return 0
    except Exception as exc:
        _fail(f"outlets.json check failed: {exc}")
        return 1


def check_env_vars() -> int:
    import os

    _header("[4] Environment variables")
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (
        os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_KEY", "").strip()
    )
    if not url:
        _fail("SUPABASE_URL is missing or empty")
        return 2
    _ok(f"SUPABASE_URL present ({url})")
    if not key:
        _fail("SUPABASE_SECRET_KEY (or fallback) is missing or empty")
        return 2
    _ok(f"SUPABASE_*_KEY present (***{key[-4:]})")
    return 0


def check_supabase_connection() -> int:
    _header("[5] Supabase connection")
    try:
        from src.db import SupabaseDb

        db = SupabaseDb()
        version = db.get_schema_version()
        _ok(f"Connected; schema_version = {version}")
        return 0
    except Exception as exc:
        _fail(f"Supabase connection failed: {exc}")
        return 3


def check_schema_version() -> int:
    _header("[6] Schema version")
    try:
        from src.db import REQUIRED_SCHEMA_VERSION, SupabaseDb

        db = SupabaseDb()
        version = db.get_schema_version()
        if version < REQUIRED_SCHEMA_VERSION:
            _fail(
                f"schema_version = {version}, need >= {REQUIRED_SCHEMA_VERSION}. "
                "Re-run shared/schema.sql in the Supabase SQL Editor."
            )
            return 4
        _ok(f"Schema version {version} meets minimum {REQUIRED_SCHEMA_VERSION}")
        return 0
    except Exception as exc:
        _fail(f"Schema version check failed: {exc}")
        return 4


def check_table_access() -> int:
    _header("[7] Critical table access")
    try:
        from src.db import SupabaseDb

        db = SupabaseDb()
        db.verify_write_permission()
        _ok("All critical tables accessible")
        return 0
    except Exception as exc:
        _fail(f"Table access denied: {exc}")
        return 5


def check_gdelt_probe() -> int:
    _header("[8] GDELT DOC 2.0 probe")
    try:
        from src.gdelt_client import query_country

        # Probe with Russia since it's a high-volume, reliable country.
        # This tests: (a) gdeltdoc library works, (b) GDELT endpoint is
        # reachable from this host, (c) our backoff logic works.
        result = query_country("RS", hours=1, max_records=5)
        if result.is_empty:
            _warn("GDELT returned empty result for RS (Russia). "
                  "May be a temporary outage; re-run in a few minutes.")
        else:
            _ok(f"GDELT returned {len(result)} rows (duration {result.duration_seconds:.2f}s)")
        return 0
    except Exception as exc:
        _fail(f"GDELT probe failed: {exc}")
        return 6


# --- Main entry point ---

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SalientSignal pipeline pre-flight check"
    )
    parser.add_argument(
        "--skip-gdelt",
        action="store_true",
        help="Skip the GDELT network probe (faster, no network needed).",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Offline mode: skip Supabase AND GDELT checks (fastest, local only).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    print(f"{BOLD}SalientSignal pipeline pre-flight check{RESET}")
    print("=" * 56)

    # Local-only checks always run
    for check in (check_python_version, check_imports, check_outlets):
        code = check()
        if code != 0:
            _fail(f"\nPre-flight FAILED at {check.__name__}.")
            return code

    if args.offline:
        print(f"\n{GREEN}{BOLD}All offline checks passed.{RESET}")
        return 0

    # Env + Supabase checks
    for check in (
        check_env_vars,
        check_supabase_connection,
        check_schema_version,
        check_table_access,
    ):
        code = check()
        if code != 0:
            _fail(f"\nPre-flight FAILED at {check.__name__}.")
            return code

    # GDELT probe (optional)
    if not args.skip_gdelt:
        code = check_gdelt_probe()
        if code != 0:
            _fail("\nPre-flight FAILED at check_gdelt_probe.")
            return code

    print(f"\n{GREEN}{BOLD}All checks passed. Pipeline is ready to deploy.{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

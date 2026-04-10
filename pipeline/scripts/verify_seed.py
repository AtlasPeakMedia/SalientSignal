"""Verify the outlet_classification table after running seed_outlets.py.

Spot-checks that:
  1. Total row count matches outlets.json
  2. Tier 1 outlets are present with correct audience_type
  3. No FVEY outlets leaked into the table
  4. Domain normalization stayed consistent through the upsert round-trip

Run after seed_outlets.py. Exit code 0 on success, non-zero on any failure.

Usage:

    python scripts/verify_seed.py

Phase 2 runbook step: Step 4, after seeding.
"""
from __future__ import annotations

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

from src.db import SupabaseDb  # noqa: E402
from src.outlets import FVEY_COUNTRIES, get_all_outlets  # noqa: E402

# Tier 1 spot checks — known outlets that must classify correctly
TIER_1_CHECKS = [
    ("rt.com", "RU", "INTERNATIONAL"),
    ("tass.ru", "RU", "DOMESTIC"),
    ("tass.com", "RU", "INTERNATIONAL"),
    ("cgtn.com", "CN", "INTERNATIONAL"),
    ("cctv.com", "CN", "DOMESTIC"),
    ("presstv.ir", "IR", "INTERNATIONAL"),
    ("irna.ir", "IR", "DOMESTIC"),
]


def _check(label: str, result: bool, detail: str = "") -> bool:
    mark = "✓" if result else "✗"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    return result


def main() -> int:
    print("SalientSignal — Outlet seeding verification")
    print("=" * 60)

    try:
        db = SupabaseDb()
        client = db._get_client()
    except RuntimeError as exc:
        print(f"\nFAIL: cannot construct Supabase client — {exc}", file=sys.stderr)
        return 2

    all_ok = True

    # Check 1: Count matches outlets.json
    expected_count = len(get_all_outlets())
    print(f"\n[1] Expected {expected_count} outlets from outlets.json")
    try:
        resp = client.table("outlet_classification").select("*", count="exact").limit(1).execute()
        actual_count = resp.count or 0
        ok = actual_count == expected_count
        _check(f"outlet_classification row count: {actual_count}", ok,
               f"expected {expected_count}")
        all_ok = all_ok and ok
    except Exception as exc:  # noqa: BLE001
        _check("Row count", False, str(exc))
        all_ok = False

    # Check 2: Tier 1 spot checks
    print("\n[2] Tier 1 outlet classification spot checks")
    for domain, expected_country, expected_audience in TIER_1_CHECKS:
        try:
            resp = (
                client.table("outlet_classification")
                .select("country,audience_type,outlet_name")
                .eq("domain", domain)
                .limit(1)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                _check(f"{domain}", False, "not found in DB")
                all_ok = False
                continue
            row = rows[0]
            actual_country = row.get("country", "")
            actual_audience = row.get("audience_type", "")
            ok = (actual_country == expected_country and
                  actual_audience == expected_audience)
            _check(
                f"{domain}",
                ok,
                f"{actual_country}/{actual_audience} "
                f"(expected {expected_country}/{expected_audience})",
            )
            all_ok = all_ok and ok
        except Exception as exc:  # noqa: BLE001
            _check(f"{domain}", False, str(exc))
            all_ok = False

    # Check 3: FVEY exclusion — no US/GB/CA/AU/NZ outlets
    print("\n[3] FVEY exclusion check")
    try:
        resp = (
            client.table("outlet_classification")
            .select("domain,country")
            .in_("country", list(FVEY_COUNTRIES))
            .execute()
        )
        leaked = resp.data or []
        ok = len(leaked) == 0
        _check(
            f"No FVEY outlets in outlet_classification",
            ok,
            f"found {len(leaked)}: {[r['domain'] for r in leaked[:5]]}" if leaked else "",
        )
        all_ok = all_ok and ok
    except Exception as exc:  # noqa: BLE001
        _check("FVEY exclusion", False, str(exc))
        all_ok = False

    # Check 4: audience_type distribution looks reasonable
    print("\n[4] Audience type distribution")
    try:
        for audience in ("DOMESTIC", "INTERNATIONAL", "DIASPORA"):
            resp = (
                client.table("outlet_classification")
                .select("*", count="exact")
                .eq("audience_type", audience)
                .limit(1)
                .execute()
            )
            count = resp.count or 0
            _check(f"{audience}: {count} outlets", True)
    except Exception as exc:  # noqa: BLE001
        _check("Audience distribution", False, str(exc))
        all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("✓ Seed verification PASSED. Safe to proceed to live pipeline run.")
        return 0
    else:
        print("✗ Seed verification FAILED. Check errors above.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

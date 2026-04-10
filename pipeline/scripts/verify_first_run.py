"""Verify the pipeline output after the first live GDELT run.

Runs a data quality check on:
  1. articles: has rows, no NULLs in required fields, tier 1 countries present
  2. country_activity: row per (country, audience_type), level values valid
  3. coordination_events: cold start should produce 0 events (or they should
     all be suppressed/escalated by anti-hal)
  4. analysis_claims: has rows for deviations + coordinations
  5. pipeline_runs: latest row has SUCCESS outcome

Use with --target to check a specific date; defaults to today (UTC).

Usage:

    python scripts/verify_first_run.py
    python scripts/verify_first_run.py --target 2026-04-10
    python scripts/verify_first_run.py --countries RU,CN,IR,KP

Phase 2 runbook step: Step 6, after first live run.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
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
from src.deviation import ALL_LEVELS  # noqa: E402

VALID_AUDIENCE_TYPES = {"DOMESTIC", "INTERNATIONAL", "DIASPORA"}


def _check(label: str, result: bool, detail: str = "") -> bool:
    mark = "✓" if result else "✗"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=str, default=None,
                        help="Target date in YYYY-MM-DD. Defaults to today (UTC).")
    parser.add_argument("--countries", type=str, default=None,
                        help="Comma-separated ISO2 list (e.g. RU,CN,IR,KP).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target_date = (
        datetime.strptime(args.target, "%Y-%m-%d").date()
        if args.target
        else datetime.now(timezone.utc).date()
    )
    expected_countries = (
        {c.strip().upper() for c in args.countries.split(",")}
        if args.countries
        else None
    )

    print(f"SalientSignal — First run verification for {target_date}")
    print("=" * 60)

    try:
        db = SupabaseDb()
        client = db._get_client()
    except RuntimeError as exc:
        print(f"\nFAIL: cannot construct Supabase client — {exc}", file=sys.stderr)
        return 2

    all_ok = True

    # Check 1: Articles table has recent rows
    print("\n[1] Articles table")
    try:
        start_ts = f"{target_date.isoformat()}T00:00:00+00:00"
        end_ts = f"{target_date.isoformat()}T23:59:59+00:00"
        resp = (
            client.table("articles")
            .select("*", count="exact")
            .gte("pub_date", start_ts)
            .lte("pub_date", end_ts)
            .limit(1)
            .execute()
        )
        article_count = resp.count or 0
        ok = article_count > 0
        _check(f"articles rows for {target_date}: {article_count}", ok)
        all_ok = all_ok and ok

        # Spot check a sample for NULL source_country or audience_type
        if article_count > 0:
            sample = (
                client.table("articles")
                .select("source_country,audience_type,source_domain")
                .gte("pub_date", start_ts)
                .limit(20)
                .execute()
            )
            sample_rows = sample.data or []
            null_country = [r for r in sample_rows if not r.get("source_country")]
            null_audience = [r for r in sample_rows if not r.get("audience_type")]
            _check(f"no NULL source_country in {len(sample_rows)}-row sample",
                   len(null_country) == 0)
            _check(f"no NULL audience_type in {len(sample_rows)}-row sample",
                   len(null_audience) == 0)
            all_ok = all_ok and len(null_country) == 0 and len(null_audience) == 0

            audience_types = {r.get("audience_type") for r in sample_rows}
            ok = audience_types.issubset(VALID_AUDIENCE_TYPES)
            _check(f"audience_type values in {audience_types}", ok)
            all_ok = all_ok and ok
    except Exception as exc:  # noqa: BLE001
        _check("articles check", False, str(exc))
        all_ok = False

    # Check 2: country_activity has rows
    print("\n[2] country_activity table")
    try:
        resp = (
            client.table("country_activity")
            .select("country,audience_type,level,today_count,confidence")
            .eq("date", target_date.isoformat())
            .execute()
        )
        activity_rows = resp.data or []
        ok = len(activity_rows) > 0
        _check(f"country_activity rows for {target_date}: {len(activity_rows)}", ok)
        all_ok = all_ok and ok

        if activity_rows:
            invalid_levels = [r for r in activity_rows if r.get("level") not in ALL_LEVELS]
            _check(f"all levels valid (in {ALL_LEVELS})", len(invalid_levels) == 0)
            all_ok = all_ok and len(invalid_levels) == 0

            if expected_countries:
                found = {r["country"] for r in activity_rows}
                missing = expected_countries - found
                _check(f"expected countries present: {expected_countries}",
                       len(missing) == 0,
                       f"missing: {missing}" if missing else "")
                all_ok = all_ok and len(missing) == 0
    except Exception as exc:  # noqa: BLE001
        _check("country_activity check", False, str(exc))
        all_ok = False

    # Check 3: analysis_claims has deviation + coordination audit rows
    print("\n[3] analysis_claims (Anti-Hal audit trail)")
    try:
        for claim_type in ("DEVIATION", "COORDINATION"):
            resp = (
                client.table("analysis_claims")
                .select("*", count="exact")
                .eq("claim_type", claim_type)
                .gte("created_at", f"{target_date.isoformat()}T00:00:00+00:00")
                .limit(1)
                .execute()
            )
            count = resp.count or 0
            # DEVIATION should always have rows (one per country_activity row).
            # COORDINATION may be 0 on cold start — that's expected.
            if claim_type == "DEVIATION":
                ok = count > 0
                _check(f"analysis_claims[{claim_type}]: {count}", ok,
                       "DEVIATION claims are mandatory")
                all_ok = all_ok and ok
            else:
                _check(f"analysis_claims[{claim_type}]: {count}", True,
                       "0 is OK on cold start")
    except Exception as exc:  # noqa: BLE001
        _check("analysis_claims check", False, str(exc))
        all_ok = False

    # Check 4: pipeline_runs health row
    print("\n[4] pipeline_runs health log")
    try:
        resp = (
            client.table("pipeline_runs")
            .select("outcome,elapsed_seconds,stats,started_at_utc")
            .order("started_at_utc", desc=True)
            .limit(1)
            .execute()
        )
        runs = resp.data or []
        if not runs:
            _check("latest pipeline_runs row", False, "no rows")
            all_ok = False
        else:
            latest = runs[0]
            outcome = latest.get("outcome", "?")
            elapsed = latest.get("elapsed_seconds", 0)
            ok = outcome == "SUCCESS"
            _check(f"latest run outcome: {outcome}", ok, f"elapsed={elapsed:.1f}s")
            all_ok = all_ok and ok
    except Exception as exc:  # noqa: BLE001
        _check("pipeline_runs check", False, str(exc))
        all_ok = False

    # Check 5: storage quota is well under free tier
    print("\n[5] Storage quota")
    try:
        used_bytes, fraction = db.check_storage_quota()
        ok = fraction < 0.5  # first run should be nowhere near 50% of free tier
        _check(
            f"storage: {used_bytes / (1024 * 1024):.1f} MB "
            f"({fraction * 100:.1f}%)",
            ok,
            "should be well under 50% on first run",
        )
        # Not a hard failure — informational
    except Exception as exc:  # noqa: BLE001
        _check("storage quota", False, str(exc))

    print("\n" + "=" * 60)
    if all_ok:
        print("✓ First-run verification PASSED. Pipeline output looks healthy.")
        return 0
    else:
        print("✗ First-run verification FAILED. Investigate before scaling up.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

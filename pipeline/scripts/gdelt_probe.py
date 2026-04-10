"""GDELT rate limit + schema reconnaissance probe.

Run this BEFORE the first live pipeline execution. The script makes
10 sequential GDELT queries against a target country and records:

  - Response times (p50, p95, max)
  - Empty vs populated results
  - Actual DataFrame column schema
  - Sample domains returned (to validate outlets.json hits)
  - Any rate limit errors (429s)

Saves the result to pipeline/logs/gdelt_probe_{timestamp}.json so operators
can audit the pipeline's expected behavior before committing to a full
scale-up run.

Usage:

    python scripts/gdelt_probe.py --country=RU
    python scripts/gdelt_probe.py --country=RU --hours=6 --queries=10

Phase 2 runbook step: Step 3, GDELT reconnaissance.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
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

from src.countries import iso_to_fips  # noqa: E402
from src.gdelt_client import REQUIRED_GDELT_COLUMNS, query_country  # noqa: E402
from src.outlets import get_outlet  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", type=str, default="RU",
                        help="ISO 3166-1 alpha-2 code (default: RU).")
    parser.add_argument("--hours", type=int, default=1,
                        help="GDELT time window in hours (default: 1).")
    parser.add_argument("--queries", type=int, default=10,
                        help="Number of sequential queries to run (default: 10).")
    parser.add_argument("--sleep", type=float, default=0.5,
                        help="Seconds to sleep between queries (default: 0.5).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    iso = args.country.upper()
    fips = iso_to_fips(iso) or iso

    print(f"SalientSignal — GDELT probe ({iso} / FIPS {fips})")
    print("=" * 60)
    print(f"Running {args.queries} queries with {args.hours}h window, "
          f"{args.sleep}s sleep between")
    print()

    durations: list[float] = []
    sample_counts: list[int] = []
    all_columns: set[str] = set()
    column_set_at_query: list[list[str]] = []
    sample_domains: list[str] = []
    errors: list[dict] = []
    outlet_hits = 0
    outlet_misses = 0

    for i in range(args.queries):
        print(f"Query {i + 1}/{args.queries}: ", end="", flush=True)
        start = time.monotonic()
        try:
            result = query_country(fips, hours=args.hours)
            durations.append(result.duration_seconds)
            df = result.df
            if df is None or df.empty:
                sample_counts.append(0)
                print(f"empty ({result.duration_seconds:.2f}s)")
                continue

            sample_counts.append(len(df))
            cols = list(df.columns)
            column_set_at_query.append(cols)
            all_columns.update(cols)

            # Capture 5 sample domains from this query
            if "domain" in df.columns and len(sample_domains) < 20:
                for domain in df["domain"].head(5).tolist():
                    if not domain or not isinstance(domain, str):
                        continue
                    if domain in sample_domains:
                        continue
                    sample_domains.append(domain)
                    # Does it resolve to an outlets.json entry?
                    if get_outlet(domain):
                        outlet_hits += 1
                    else:
                        outlet_misses += 1
                    if len(sample_domains) >= 20:
                        break

            print(f"{len(df)} rows ({result.duration_seconds:.2f}s, "
                  f"retries={result.retries})")
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - start
            errors.append({
                "query": i + 1,
                "error": str(exc),
                "elapsed_seconds": elapsed,
            })
            print(f"ERROR: {exc} ({elapsed:.2f}s)")

        if i < args.queries - 1:
            time.sleep(args.sleep)

    print()
    print("=" * 60)
    print("GDELT Probe Summary")
    print("=" * 60)

    if durations:
        p50 = statistics.median(durations)
        p95 = statistics.quantiles(durations, n=20)[18] if len(durations) >= 2 else durations[0]
        max_d = max(durations)
        print(f"  Latency: p50={p50:.2f}s  p95={p95:.2f}s  max={max_d:.2f}s")

    if sample_counts:
        empty_count = sum(1 for c in sample_counts if c == 0)
        print(f"  Responses: {len(sample_counts)} queries, "
              f"{empty_count} empty, "
              f"avg rows: {statistics.mean(sample_counts):.1f}")

    if errors:
        print(f"  Errors: {len(errors)} of {args.queries} queries failed")
    else:
        print(f"  Errors: none")

    # Schema check
    print(f"\n  Columns returned: {sorted(all_columns)}")
    missing_required = REQUIRED_GDELT_COLUMNS - all_columns
    if missing_required:
        print(f"  ⚠ MISSING required columns: {sorted(missing_required)}")
    else:
        print(f"  ✓ All {len(REQUIRED_GDELT_COLUMNS)} required columns present")

    # Outlets match rate
    total_samples = outlet_hits + outlet_misses
    if total_samples > 0:
        hit_rate = outlet_hits / total_samples
        print(f"\n  outlets.json hit rate: {outlet_hits}/{total_samples} "
              f"({hit_rate * 100:.1f}%)")
        print(f"  Sample domains ({len(sample_domains)}):")
        for d in sample_domains[:15]:
            hit = "✓" if get_outlet(d) else "✗"
            print(f"    [{hit}] {d}")

    # Write audit log
    logs_dir = PIPELINE_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = logs_dir / f"gdelt_probe_{iso}_{ts}.json"

    audit = {
        "timestamp": ts,
        "country_iso": iso,
        "country_fips": fips,
        "hours": args.hours,
        "queries_attempted": args.queries,
        "sleep_seconds": args.sleep,
        "durations_seconds": durations,
        "latency_p50": statistics.median(durations) if durations else None,
        "latency_max": max(durations) if durations else None,
        "sample_counts": sample_counts,
        "avg_rows_per_query": statistics.mean(sample_counts) if sample_counts else 0,
        "columns_observed": sorted(all_columns),
        "missing_required_columns": sorted(missing_required),
        "sample_domains": sample_domains,
        "outlet_hit_rate": hit_rate if total_samples > 0 else None,
        "outlet_hits": outlet_hits,
        "outlet_misses": outlet_misses,
        "errors": errors,
    }
    with log_path.open("w") as f:
        json.dump(audit, f, indent=2, default=str)
    print(f"\n  Audit log written to: {log_path}")

    # Exit code: fail if missing columns or all queries errored
    if missing_required:
        print("\n✗ PROBE FAILED: GDELT schema drift detected.")
        return 1
    if len(errors) == args.queries:
        print("\n✗ PROBE FAILED: every query errored.")
        return 2
    if total_samples > 0 and (outlet_hits / total_samples) < 0.3:
        print("\n⚠ WARNING: outlets.json hit rate < 30%. "
              "Domain normalization may need work before full scale-up.")
    print("\n✓ PROBE COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""GDELT GKG 2.0 theme backfill — CLI orchestrator.

Downloads a date range of 15-min GKG files from the GDELT bulk CDN, filters
rows to our monitored domains, aggregates themes by (country, audience,
period_type, period_start), and writes a local JSON file. Like
`run_backfill.py` for the volume data, this script never touches Supabase;
a separate `import_gkg_backfill.py` validates the JSON and upserts.

Typical usage:

    # Smoke test: one full day, monthly aggregation only, output to JSON
    python -m pipeline.scripts.run_gkg_backfill \\
        --start-date 2026-04-09 \\
        --end-date 2026-04-09 \\
        --period monthly \\
        --output-json pipeline/data/theme_backfill_2026-04-09.json

    # Full 15-month monthly backfill (~30 min with parallelism)
    python -m pipeline.scripts.run_gkg_backfill \\
        --start-date 2025-01-01 \\
        --end-date 2026-04-09 \\
        --period monthly \\
        --output-json pipeline/data/theme_backfill_monthly.json \\
        --parallelism 20

Parallelism note: the GKG CDN is Google Cloud Storage. Internal testing shows
~20 concurrent fetches is the sweet spot (no throttling, saturates a home
connection). Going above 30 starts to see occasional 500s from GCS.

All fetches happen in a ThreadPoolExecutor — not asyncio — because the
downstream CSV parsing is CPU-bound and GIL release in urllib is fine for
this workload.

Output JSON shape:

    {
        "metadata": {
            "start_date": "2025-01-01",
            "end_date": "2026-04-09",
            "period_type": "monthly",
            "generated_at": "2026-04-11T02:17:00Z",
            "outlet_count": 301,
            "stats": {
                "files_attempted": 44544,
                "files_fetched": 44500,
                "files_skipped_404": 44,
                "files_errored": 0,
                "total_rows_seen": 55123456,
                "matched_rows": 776382,
                "unique_matched_articles": 687291,
                "buckets_produced": 8_452,
                "duration_seconds": 1833.2
            }
        },
        "theme_buckets": [ { ...ThemeBucket.to_dict()... }, ... ]
    }
"""
from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path

# Put pipeline/ on sys.path so `from src.xxx import ...` works both when
# run as `python -m pipeline.scripts.run_gkg_backfill` from the repo root
# AND as `python pipeline/scripts/run_gkg_backfill.py`. Matches the
# convention in run_backfill.py.
THIS_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = THIS_DIR.parent
sys.path.insert(0, str(PIPELINE_DIR))

try:
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv(PIPELINE_DIR / ".env")
except ImportError:
    pass  # dotenv is optional — env vars can come from the process environment

from src.gkg_client import (  # noqa: E402
    GkgFileResult,
    GkgRow,
    fetch_gkg_file,
    iter_15min_slices,
)
from src.outlets import load_outlets  # noqa: E402
from src.theme_aggregator import (  # noqa: E402
    DEFAULT_MIN_ARTICLE_COUNT,
    DEFAULT_TOP_N_PER_BUCKET,
    PeriodType,
    aggregate_themes,
)

logger = logging.getLogger("run_gkg_backfill")

# ThreadPool default — tested sweet spot for GCS + home bandwidth.
DEFAULT_PARALLELISM = 20

# Checkpoint cadence: log progress every N fetched files so long runs don't
# look hung from a tailing terminal.
PROGRESS_LOG_EVERY = 200

# Graceful-interrupt sentinel. When set, the main loop stops dispatching new
# fetches and drains the ones in flight before writing a partial JSON. Set
# by the SIGINT handler.
_interrupted = threading.Event()


def _handle_sigint(signum, frame):
    if _interrupted.is_set():
        logger.warning("Second SIGINT — exiting immediately")
        sys.exit(1)
    logger.warning("SIGINT received — will drain in-flight fetches then write partial JSON")
    _interrupted.set()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download GKG 2.0 bulk files, aggregate themes, emit JSON.",
    )
    p.add_argument(
        "--start-date", required=True,
        help="Inclusive start date (YYYY-MM-DD). The first 15-min slice is 00:00 UTC of this date.",
    )
    p.add_argument(
        "--end-date", required=True,
        help="Inclusive end date (YYYY-MM-DD). The last 15-min slice is 23:45 UTC of this date.",
    )
    p.add_argument(
        "--period", default="monthly", choices=["daily", "weekly", "monthly"],
        help="Aggregation bucket granularity (default: monthly).",
    )
    p.add_argument(
        "--output-json", required=True,
        help="Path to write the aggregated theme bucket JSON.",
    )
    p.add_argument(
        "--parallelism", type=int, default=DEFAULT_PARALLELISM,
        help=f"Concurrent GKG downloads (default: {DEFAULT_PARALLELISM}).",
    )
    p.add_argument(
        "--top-n", type=int, default=DEFAULT_TOP_N_PER_BUCKET,
        help=f"Top N themes per bucket (default: {DEFAULT_TOP_N_PER_BUCKET}).",
    )
    p.add_argument(
        "--min-article-count", type=int, default=DEFAULT_MIN_ARTICLE_COUNT,
        help=f"Drop themes with fewer mentions (default: {DEFAULT_MIN_ARTICLE_COUNT}).",
    )
    p.add_argument(
        "--force", action="store_true",
        help="Overwrite --output-json if it already exists.",
    )
    p.add_argument(
        "--verbose", action="store_true",
        help="Enable DEBUG logging.",
    )
    p.add_argument(
        "--outlets-file", default=None,
        help="Override path to outlets.json (default: pipeline/data/outlets.json).",
    )
    p.add_argument(
        "--max-files", type=int, default=None,
        help="Cap total files fetched — useful for smoke tests. Default: no cap.",
    )
    return p.parse_args()


def _validate_dates(start_s: str, end_s: str) -> tuple[date, date]:
    try:
        start = datetime.strptime(start_s, "%Y-%m-%d").date()
        end = datetime.strptime(end_s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"Invalid date format (want YYYY-MM-DD): {exc}")
    if end < start:
        raise SystemExit(f"--end-date {end} is before --start-date {start}")
    return start, end


def _build_slice_list(
    start: date, end: date, max_files: int | None
) -> list[datetime]:
    """Produce the full list of 15-min UTC timestamps to fetch."""
    start_dt = datetime.combine(start, dtime(0, 0), tzinfo=timezone.utc)
    end_dt = datetime.combine(end, dtime(23, 45), tzinfo=timezone.utc)
    slices = list(iter_15min_slices(start_dt, end_dt))
    if max_files is not None and len(slices) > max_files:
        logger.info("Capping slice list: %d -> %d (max_files)", len(slices), max_files)
        slices = slices[:max_files]
    return slices


def main() -> int:
    args = _parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    # Quiet the noisy urllib logger unless verbose
    if not args.verbose:
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    signal.signal(signal.SIGINT, _handle_sigint)

    start_date, end_date = _validate_dates(args.start_date, args.end_date)

    output_path = Path(args.output_json)
    if output_path.exists() and not args.force:
        logger.error(
            "%s already exists. Use --force to overwrite, or pick a different path.",
            output_path,
        )
        return 2
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load outlets + monitored domain set
    outlets_path = Path(args.outlets_file) if args.outlets_file else None
    outlets_map = load_outlets(outlets_path)
    domain_set = set(outlets_map.keys())
    logger.info("Loaded %d monitored domains", len(domain_set))

    slices = _build_slice_list(start_date, end_date, args.max_files)
    logger.info(
        "Queueing %d 15-min slices for %s..%s (period=%s, parallelism=%d)",
        len(slices), start_date, end_date, args.period, args.parallelism,
    )

    period_type: PeriodType = args.period  # type: ignore[assignment]

    # Stats counters — incremented from multiple threads via lock
    stats = {
        "files_attempted": 0,
        "files_fetched": 0,
        "files_skipped_404": 0,
        "files_errored": 0,
        "total_rows_seen": 0,
        "matched_rows": 0,
    }
    stats_lock = threading.Lock()
    all_rows: list[GkgRow] = []
    all_rows_lock = threading.Lock()

    start_ts = time.monotonic()

    def _process_one(slice_time: datetime) -> None:
        if _interrupted.is_set():
            return
        result: GkgFileResult = fetch_gkg_file(slice_time, domain_set)
        with stats_lock:
            stats["files_attempted"] += 1
            stats["total_rows_seen"] += result.total_rows_seen
            if result.skipped:
                if result.error == "404":
                    stats["files_skipped_404"] += 1
                else:
                    stats["files_errored"] += 1
            else:
                stats["files_fetched"] += 1
                stats["matched_rows"] += result.matched_rows
        if result.rows:
            with all_rows_lock:
                all_rows.extend(result.rows)

    # Execute the downloads concurrently
    with ThreadPoolExecutor(max_workers=args.parallelism) as executor:
        futures = []
        for slice_time in slices:
            if _interrupted.is_set():
                break
            futures.append(executor.submit(_process_one, slice_time))

        # Log progress as futures complete
        completed = 0
        for _f in as_completed(futures):
            completed += 1
            if completed % PROGRESS_LOG_EVERY == 0:
                with stats_lock:
                    elapsed = time.monotonic() - start_ts
                    rate = stats["files_attempted"] / elapsed if elapsed > 0 else 0
                    eta = (len(slices) - completed) / rate if rate > 0 else 0
                    logger.info(
                        "[progress %d/%d] fetched=%d 404=%d err=%d matched_rows=%d  rate=%.1f/s eta=%.0fs",
                        completed, len(slices),
                        stats["files_fetched"], stats["files_skipped_404"],
                        stats["files_errored"], stats["matched_rows"],
                        rate, eta,
                    )

    duration = time.monotonic() - start_ts
    with stats_lock:
        final_stats = dict(stats)
    final_stats["duration_seconds"] = round(duration, 1)

    # Aggregate
    logger.info(
        "Fetch phase complete: %d files attempted, %d matched rows in %.1fs. Aggregating...",
        final_stats["files_attempted"], final_stats["matched_rows"], duration,
    )

    buckets = aggregate_themes(
        all_rows,
        period_type=period_type,
        top_n=args.top_n,
        min_article_count=args.min_article_count,
    )
    final_stats["unique_matched_articles"] = len({
        (r.domain, r.url) for r in all_rows
    })
    final_stats["buckets_produced"] = len(buckets)

    # Write JSON output
    output = {
        "metadata": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "period_type": period_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "outlet_count": len(domain_set),
            "top_n": args.top_n,
            "min_article_count": args.min_article_count,
            "parallelism": args.parallelism,
            "interrupted": _interrupted.is_set(),
            "stats": final_stats,
        },
        "theme_buckets": [b.to_dict() for b in buckets],
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, separators=(",", ":"))
    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(
        "Wrote %d theme buckets to %s (%.2f MB)",
        len(buckets), output_path, size_mb,
    )

    # Summary block
    print()
    print("=== GKG theme backfill summary ===")
    print(f"  Window:       {start_date} .. {end_date} ({period_type})")
    print(f"  Files:        {final_stats['files_fetched']} fetched, "
          f"{final_stats['files_skipped_404']} 404, {final_stats['files_errored']} errored")
    print(f"  Rows seen:    {final_stats['total_rows_seen']:,}")
    print(f"  Matched:      {final_stats['matched_rows']:,} rows "
          f"({final_stats['unique_matched_articles']:,} unique articles)")
    print(f"  Buckets:      {final_stats['buckets_produced']:,}")
    print(f"  Duration:     {final_stats['duration_seconds']:.1f}s")
    print(f"  Output:       {output_path}")
    if _interrupted.is_set():
        print("  **PARTIAL**: run was interrupted; re-run to complete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

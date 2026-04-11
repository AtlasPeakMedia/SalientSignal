"""GKG theme hourly incremental ingestion.

Runs on Render's cron alongside run_pipeline.py. Fetches the past hour's
GKG 2.0 bulk files (four 15-min slices), filters to our monitored domains,
aggregates by (country, audience, day | week | current-month), and upserts
directly into Supabase's country_theme_{daily, weekly, monthly} tables.

Design:
    - Uses a sliding "now" window instead of a fixed date range, so this
      script is idempotent: running it at 14:07 UTC fetches ~13:00-14:00
      UTC files, running it at 14:45 UTC fetches ~13:45-14:45 UTC files,
      and overlapping fetches deduplicate via the upsert primary key.
    - The daily rollup uses today's date. Previous days aren't touched —
      the 15-month backfill already populated them, and daily data rolls
      out of country_theme_daily after 30 days via a future purge job
      (not implemented here).
    - The monthly and weekly rollups ALSO get updated, but ONLY for the
      current period. Historic months/weeks are frozen by the 15-month
      backfill.
    - If Supabase is unreachable or the schema v3 tables don't exist yet,
      the script logs clearly and exits 0 instead of raising — the main
      pipeline cron shouldn't fail just because themes aren't set up.
    - Hard time budget of 240 seconds (4 minutes) so this never overlaps
      the next cron tick.

Typical runtime: 10-20 seconds for ~4 files + upsert.

Not wired into render.yaml yet — the render.yaml ships a single cron
invoking run_pipeline.py. To run themes hourly, either:
    (a) add a second cron service in render.yaml (preferred)
    (b) chain this after run_pipeline.py in a wrapper script
    (c) run it manually from a laptop periodically

Option (a) is implemented in the updated render.yaml that ships with this
script.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv(REPO_ROOT / "pipeline" / ".env")
except ImportError:
    pass

from pipeline.src.db import DbError, SupabaseDb  # noqa: E402
from pipeline.src.gkg_client import (  # noqa: E402
    GkgRow,
    fetch_gkg_file,
)
from pipeline.src.outlets import load_outlets  # noqa: E402
from pipeline.src.theme_aggregator import (  # noqa: E402
    DEFAULT_MIN_ARTICLE_COUNT,
    DEFAULT_TOP_N_PER_BUCKET,
    aggregate_themes,
)

logger = logging.getLogger("run_gkg_hourly")

DEFAULT_PARALLELISM = 4
DEFAULT_LOOKBACK_MINUTES = 75  # Slightly more than 60 min to tolerate cron drift
DEFAULT_TIME_BUDGET_SECONDS = 240

# PostgREST code for "relation does not exist" — schema v3 not applied yet
POSTGREST_MISSING_TABLE_CODE = "42P01"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Hourly GKG theme incremental ingestion",
    )
    p.add_argument(
        "--lookback-minutes", type=int, default=DEFAULT_LOOKBACK_MINUTES,
        help=(
            "How far back to fetch GKG files from now. Default 75 min "
            "(slightly over 60 min for cron drift tolerance)."
        ),
    )
    p.add_argument(
        "--parallelism", type=int, default=DEFAULT_PARALLELISM,
        help=f"Concurrent GKG downloads (default: {DEFAULT_PARALLELISM}).",
    )
    p.add_argument(
        "--time-budget", type=int, default=DEFAULT_TIME_BUDGET_SECONDS,
        help=f"Hard time budget in seconds (default: {DEFAULT_TIME_BUDGET_SECONDS}).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Fetch + aggregate, but don't upsert to Supabase.",
    )
    p.add_argument(
        "--verbose", action="store_true",
        help="Enable DEBUG logging.",
    )
    p.add_argument(
        "--now", default=None,
        help=(
            "Override 'now' for testing. ISO-8601 UTC timestamp like "
            "2026-04-10T14:07:00Z. Default: actual wall-clock UTC."
        ),
    )
    return p.parse_args()


def _now_utc(override: str | None) -> datetime:
    if override:
        # Accept 2026-04-10T14:07:00Z or with offset
        s = override.rstrip("Z")
        try:
            return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise SystemExit(f"Invalid --now timestamp: {exc}") from exc
    return datetime.now(timezone.utc)


def _slices_in_lookback(
    now: datetime, lookback_minutes: int
) -> list[datetime]:
    """Compute the 15-min slice timestamps to fetch in the lookback window.

    Picks every :00, :15, :30, :45 timestamp between (now - lookback) and now.
    Excludes the current slice if we're still inside its 15-min window — GDELT
    hasn't published that file yet. GDELT typically publishes files ~5 minutes
    after the slice boundary; we use a 7-minute safety margin.
    """
    safety_margin = timedelta(minutes=7)
    latest_available = now - safety_margin
    # Floor latest_available to the previous 15-min boundary
    lm = latest_available.minute - (latest_available.minute % 15)
    latest_slice = latest_available.replace(minute=lm, second=0, microsecond=0)

    earliest_slice = latest_slice - timedelta(minutes=lookback_minutes)
    # Floor earliest to a 15-min boundary
    em = earliest_slice.minute - (earliest_slice.minute % 15)
    earliest_slice = earliest_slice.replace(minute=em, second=0, microsecond=0)

    slices: list[datetime] = []
    current = earliest_slice
    while current <= latest_slice:
        slices.append(current)
        current = current + timedelta(minutes=15)
    return slices


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    if not args.verbose:
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    now = _now_utc(args.now)
    slices = _slices_in_lookback(now, args.lookback_minutes)
    if not slices:
        logger.info("No slices in lookback window. Nothing to do.")
        return 0

    logger.info(
        "Hourly theme incremental: now=%s lookback=%dmin slices=%d",
        now.isoformat(), args.lookback_minutes, len(slices),
    )
    logger.debug("Slice list: %s", [s.strftime("%H%M") for s in slices])

    outlets_map = load_outlets()
    domain_set = set(outlets_map.keys())
    logger.info("Loaded %d monitored domains", len(domain_set))

    # Hard time budget: SIGALRM is the cleanest way on unix, but signal
    # handling inside ThreadPoolExecutor is messy. Use a simple elapsed
    # check in the completion loop instead.
    started = time.monotonic()
    deadline = started + args.time_budget

    all_rows: list[GkgRow] = []
    files_fetched = 0
    files_skipped = 0
    files_errored = 0

    with ThreadPoolExecutor(max_workers=args.parallelism) as executor:
        futures = {
            executor.submit(fetch_gkg_file, s, domain_set): s
            for s in slices
        }
        for future in as_completed(futures):
            if time.monotonic() > deadline:
                logger.warning("Time budget exceeded — aborting remaining fetches")
                for f in futures:
                    f.cancel()
                break
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Fetch failed: %s", exc)
                files_errored += 1
                continue
            if result.skipped:
                if result.error == "404":
                    files_skipped += 1
                else:
                    files_errored += 1
                    logger.warning("Skipped %s: %s", result.slice_time, result.error)
            else:
                files_fetched += 1
                all_rows.extend(result.rows)

    logger.info(
        "Fetch phase: fetched=%d skipped_404=%d errored=%d matched_rows=%d elapsed=%.1fs",
        files_fetched, files_skipped, files_errored, len(all_rows),
        time.monotonic() - started,
    )

    if not all_rows:
        logger.info("No matched rows in this window — nothing to upsert.")
        return 0

    # Aggregate into THREE buckets: daily, weekly, monthly. All three use
    # the same source rows, just different period_type groupings.
    daily_buckets = aggregate_themes(
        all_rows,
        period_type="daily",
        top_n=DEFAULT_TOP_N_PER_BUCKET,
        min_article_count=DEFAULT_MIN_ARTICLE_COUNT,
    )
    weekly_buckets = aggregate_themes(
        all_rows,
        period_type="weekly",
        top_n=DEFAULT_TOP_N_PER_BUCKET,
        min_article_count=DEFAULT_MIN_ARTICLE_COUNT,
    )
    monthly_buckets = aggregate_themes(
        all_rows,
        period_type="monthly",
        top_n=DEFAULT_TOP_N_PER_BUCKET,
        min_article_count=DEFAULT_MIN_ARTICLE_COUNT,
    )

    logger.info(
        "Aggregated: daily=%d weekly=%d monthly=%d",
        len(daily_buckets), len(weekly_buckets), len(monthly_buckets),
    )

    if args.dry_run:
        logger.info("--dry-run: not writing to DB")
        return 0

    # Upsert to Supabase
    try:
        db = SupabaseDb()
    except Exception as exc:  # noqa: BLE001
        logger.error("Cannot construct SupabaseDb: %s", exc)
        return 1

    total_upserted = 0
    for name, bucket_list, period_type in (
        ("daily", daily_buckets, "daily"),
        ("weekly", weekly_buckets, "weekly"),
        ("monthly", monthly_buckets, "monthly"),
    ):
        if not bucket_list:
            continue
        rows = [b.to_dict() for b in bucket_list]
        try:
            n = db.upsert_country_theme_batch(rows, period_type=period_type)
            total_upserted += n
            logger.info("Upserted %d rows into country_theme_%s", n, period_type)
        except DbError as exc:
            # Check for "relation does not exist" — schema v3 not applied yet
            msg = str(exc)
            if POSTGREST_MISSING_TABLE_CODE in msg or "does not exist" in msg:
                logger.warning(
                    "country_theme_%s table does not exist yet. "
                    "Apply shared/migrations/002_country_theme_tables.sql in "
                    "Supabase SQL Editor. Skipping this bucket for now.",
                    period_type,
                )
                continue
            raise  # Re-raise any other DB error for the cron to alert on

    elapsed = time.monotonic() - started
    logger.info(
        "Hourly theme incremental complete: %d rows upserted in %.1fs",
        total_upserted, elapsed,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

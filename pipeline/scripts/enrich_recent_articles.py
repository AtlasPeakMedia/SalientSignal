"""Recent-articles enrichment — Phase A5 stub.

This script is a placeholder for the "enrichment pass" described in the
Phase A5 plan: after the historical backfill populates country_activity
baselines, a separate pass should query GDELT ArtList mode for the last
30 days to populate the articles table (which drives the country-page
headline feed) and optionally refresh top_themes / top_outlets on recent
country_activity rows.

Why this is a stub today:

    The existing ``gdelt_client.query_country`` helper uses GDELT's
    ``timespan`` parameter which only queries "the last N hours from now"
    — it does NOT accept arbitrary historical date ranges. And
    ``run_pipeline`` always computes fresh baselines from ``articles``, so
    running it on historical dates would OVERWRITE the backfilled
    baseline values in country_activity with low-quality (empty articles
    table) numbers. The correct solution is either:

        1. Add a ``query_country_date_range(country_fips, start_date,
           end_date)`` helper to gdelt_client that uses GDELT's
           ``startdatetime`` / ``enddatetime`` parameters instead of
           ``timespan``, AND
        2. Add a ``skip_country_activity_upsert=True`` flag to
           run_pipeline OR refactor fetch_baseline to read historical
           counts from country_activity.today_count when available
           (instead of always going through the articles table).

    Both fixes are straightforward but out of scope for the A1-A5 commit.
    They'll land as a follow-on commit before the public launch, tracked
    as a Phase 5 item in the plan.

What the MVP launches with instead:

    * Backfill populates country_activity for Jan 1, 2025 - today with
      real baselines. Globe colors are correct. Deviation metrics are
      correct. cold_start is cleared on historical rows.
    * The articles table is empty for historical dates. Country page
      headline feeds show "no recent articles" for historical rows.
    * Once the live pipeline starts running hourly (Phase F1), it begins
      accumulating articles for today-forward, and the headline feeds
      become populated for recent dates from that point on.
    * top_themes and top_outlets stay empty on historical country_activity
      rows. The frontend handles this gracefully (shows top outlets from
      the backfill's aggregation layer when present).

How to run this script once the underlying helpers exist:

    python scripts/enrich_recent_articles.py \\
        --days 7 \\
        --backfill-json data/backfill_2025-01-01_2026-04-09.json

Acceptance test (already exists in test_import_backfill.py):

    test_preserves_backfilled_baselines — runs backfill then import, then
    verifies that the country_activity rows still have the backfilled
    baseline_mean / baseline_std / cold_start=False. Enrichment must NOT
    overwrite these.

See plan: proud-jumping-key.md Phase A5 and Phase 5 deferred items.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enrich recent articles (STUB — see module docstring).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days back from today to enrich (default: 7).",
    )
    parser.add_argument(
        "--backfill-json",
        type=str,
        default=None,
        help="Path to the run_backfill.py JSON (used to verify we don't "
        "overwrite backfilled baselines).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(
        "enrich_recent_articles: STUB (not yet implemented).\n"
        "\n"
        "Phase A5 is deferred. See the module docstring and "
        "/Users/don/.claude/plans/proud-jumping-key.md for the full\n"
        "architectural discussion and the implementation requirements:\n"
        "\n"
        "  1. Add query_country_date_range() to pipeline/src/gdelt_client.py\n"
        "  2. Refactor fetch_baseline() to prefer country_activity over articles\n"
        "     for historical windows\n"
        "  3. Add a skip_country_activity_upsert flag to run_pipeline OR write\n"
        "     a dedicated enrich path that inserts articles only\n"
        "\n"
        "Until then: the live pipeline (Phase F1 Render cron) will accumulate\n"
        "articles from the first successful run forward, populating the\n"
        "headline feed naturally. Backfilled baselines remain intact.\n"
        "\n"
        f"Requested --days={args.days}, --backfill-json={args.backfill_json}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

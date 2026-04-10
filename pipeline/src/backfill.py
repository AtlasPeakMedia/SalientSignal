"""Historical backfill module — Phase A2 of the 15-month backfill plan.

Takes an outlet list and a date range, pulls per-outlet daily publication
volumes from GDELT via ``gdelt_timeline_client``, aggregates into per-(country,
date, audience_type) daily counts, computes 30-day rolling baselines, and
produces ``country_activity`` rows ready for bulk upsert into Supabase.

Why backfill exists:
    Instead of running the live pipeline hourly and waiting 21-30 days for
    cold-start calibration, we want to pull 15 months of historical volume
    data and compute baselines retroactively. That gives us a working product
    on day 1, not day 22, and lets us validate the coordination + anti-hal
    logic against known events (Feb 24 Ukraine anniversary, Oct 7 Gaza, May 9
    Russia Victory Day, etc.) before launch.

What it does NOT do:
    * Populate the ``articles`` table. TimelineVolRaw returns aggregated
      counts, not article-level records. The A5 enrichment script runs the
      existing ArtList pipeline for the last 30 days to populate articles +
      top_themes + top_outlets for recent dates only.
    * Extract themes. TimelineVolRaw has no theme information, so
      ``top_themes`` in backfilled rows is always ``{}``. The A5 enrichment
      backfills top_themes for recent dates from real article data.
    * Run the Anti-Hallucination Agent. Anti-hal validates real-time claims
      against anniversaries, competing hypotheses, major-event heuristics.
      That logic does NOT apply to historical truth — we WANT the Feb 24 2026
      signal to show up in the globe. Backfill deliberately bypasses anti-hal;
      a future audit script can re-run it post-import if desired.

Output shape:
    ``BackfillResult.country_activity`` is a list of dicts with the exact
    same key structure as what ``pipeline.run_pipeline()`` writes at
    ``pipeline.py:600-617``, so ``import_backfill.py`` can upsert them with
    ``db.upsert_country_activity_batch()`` unchanged.

Key semantics:

    * Dates with zero activity (no outlet reported any volume) still get a
      row emitted, with ``today_count=0``. The frontend needs a row for every
      (country, audience, date) that the frontend might render.

    * Baselines are computed from the PRECEDING 30 days' worth of data
      *within the backfill window*. For the first ~30 days of the window
      we'll have fewer than 30 samples; those rows get LOW/MEDIUM confidence
      and ``cold_start=True``. Dates before the backfill window are NOT
      padded with false zeros — we'd be inventing data.

    * ``top_outlets`` is populated from the per-outlet daily counts for that
      specific (country, audience, date) bucket. Useful even without
      article-level themes because it tells you WHICH outlets surged on a
      given day.

    * ``top_themes`` is always ``{}`` — TimelineVolRaw has no theme data.
      Documented in the methodology page; enrichment handles recent dates.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from .baselines import BASELINE_WINDOW_DAYS, MIN_SAMPLE_DAYS, calculate_baseline
from .deviation import calculate_deviation
from .gdelt_timeline_client import TimelineResult, query_domain_timeline
from .outlets import OutletRecord, get_all_outlets

logger = logging.getLogger(__name__)

# Type alias for the timeline client dependency (injectable for tests).
TimelineClient = Callable[..., TimelineResult]


@dataclass
class BackfillStats:
    """Counts of what the backfill did. Included in BackfillResult + JSON output."""

    outlets_queried: int = 0
    outlets_succeeded: int = 0
    outlets_empty: int = 0  # valid zero-activity outlets (not errors)
    outlets_failed: int = 0
    outlets_skipped: int = 0  # skipped by resume_from
    days_covered: int = 0
    country_activity_rows: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "outlets_queried": self.outlets_queried,
            "outlets_succeeded": self.outlets_succeeded,
            "outlets_empty": self.outlets_empty,
            "outlets_failed": self.outlets_failed,
            "outlets_skipped": self.outlets_skipped,
            "days_covered": self.days_covered,
            "country_activity_rows": self.country_activity_rows,
        }


@dataclass
class BackfillResult:
    """Everything run_backfill() produced: ready for JSON export + DB import."""

    stats: BackfillStats
    country_activity: list[dict[str, Any]]
    # (domain, date) -> raw volume. Retained so import_backfill can audit
    # the aggregation if any country_activity row looks suspicious.
    raw_outlet_daily_counts: dict[tuple[str, date], int]
    failures: list[tuple[str, str]] = field(default_factory=list)


def _date_range(start_date: date, end_date: date) -> list[date]:
    """Inclusive date range [start_date, end_date]."""
    days = (end_date - start_date).days
    return [start_date + timedelta(days=i) for i in range(days + 1)]


def _filter_outlets_for_resume(
    outlets: list[OutletRecord],
    resume_from: str | None,
) -> tuple[list[OutletRecord], int]:
    """Return (outlets_to_process, skipped_count).

    ``resume_from`` semantics: "start with this outlet". Outlets alphabetically
    STRICTLY BEFORE ``resume_from`` are skipped; the named outlet itself is
    re-queried (safe for a crashed mid-outlet run). Sorted alphabetically so
    the skip behavior is deterministic.
    """
    sorted_outlets = sorted(outlets, key=lambda o: o.domain)
    if not resume_from:
        return sorted_outlets, 0
    cutoff = resume_from.lower().strip()
    processed = [o for o in sorted_outlets if o.domain >= cutoff]
    skipped = len(sorted_outlets) - len(processed)
    return processed, skipped


def _query_outlets(
    outlets: list[OutletRecord],
    *,
    start_date: date,
    end_date: date,
    timeline_client: TimelineClient,
    stats: BackfillStats,
    failures: list[tuple[str, str]],
    verbose: bool,
    progress_every: int = 10,
) -> dict[str, dict[date, int]]:
    """Query GDELT TimelineVolRaw for every outlet in ``outlets``.

    Returns ``{domain: {date: volume}}``. Handles exceptions per-outlet so
    one failure never halts the run — failed domains are logged to the
    ``failures`` list and counted separately in stats.
    """
    per_outlet_daily: dict[str, dict[date, int]] = {}
    total = len(outlets)
    for idx, outlet in enumerate(outlets, start=1):
        stats.outlets_queried += 1
        try:
            result = timeline_client(
                outlet.domain,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:  # noqa: BLE001 — gdeltdoc raises a variety of types
            stats.outlets_failed += 1
            failures.append((outlet.domain, str(exc)))
            logger.warning(
                "[%d/%d] backfill query failed for %s: %s",
                idx,
                total,
                outlet.domain,
                exc,
            )
            continue

        stats.outlets_succeeded += 1
        daily = {row.date: row.volume_raw for row in result.rows}
        per_outlet_daily[outlet.domain] = daily

        if result.is_empty:
            stats.outlets_empty += 1

        if verbose or idx % progress_every == 0:
            logger.info(
                "[%d/%d] domain=%s rows=%d total_volume=%d retries=%d",
                idx,
                total,
                outlet.domain,
                len(result.rows),
                result.total_volume,
                result.retries,
            )

    return per_outlet_daily


def _aggregate_per_bucket(
    outlets: list[OutletRecord],
    per_outlet_daily: dict[str, dict[date, int]],
) -> tuple[
    dict[tuple[str, str], dict[date, int]],
    dict[tuple[str, str, date], list[tuple[str, int]]],
]:
    """Collapse per-outlet daily counts into per-(country, audience) time series.

    Returns:
        series: ``(country, audience_type) -> {date: summed_count}``
        contributions: ``(country, audience_type, date) -> [(domain, count), ...]``
    """
    series: dict[tuple[str, str], dict[date, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    contributions: dict[tuple[str, str, date], list[tuple[str, int]]] = defaultdict(
        list
    )

    for outlet in outlets:
        daily = per_outlet_daily.get(outlet.domain, {})
        for day, count in daily.items():
            if count < 0:
                logger.debug("Negative count for %s %s — skipping", outlet.domain, day)
                continue
            series[(outlet.country, outlet.audience_type)][day] += count
            if count > 0:
                contributions[(outlet.country, outlet.audience_type, day)].append(
                    (outlet.domain, count)
                )

    return series, contributions


def _registered_buckets(outlets: list[OutletRecord]) -> set[tuple[str, str]]:
    """Every (country, audience_type) tuple with at least one registered outlet.

    We emit rows for every registered bucket × every date in the window,
    not just buckets that reported activity. A "country went silent" row
    is still signal.
    """
    return {(o.country, o.audience_type) for o in outlets}


def _build_preceding_counts(
    daily_counts: dict[date, int],
    target_date: date,
    backfill_start: date,
    window_days: int,
) -> list[int]:
    """Gather preceding-window counts for baseline calculation.

    Only includes dates WITHIN the backfill window. Dates before
    ``backfill_start`` are excluded (we had no data then, so padding them
    with zeros would invent a false baseline).

    For target_date = backfill_start, this returns []. For target_date =
    backfill_start + 1, it returns 1 count. For target_date >= backfill_start
    + window_days, it returns ``window_days`` counts.
    """
    counts = []
    for i in range(1, window_days + 1):
        d = target_date - timedelta(days=i)
        if d >= backfill_start:
            counts.append(daily_counts.get(d, 0))
    return counts


def _build_activity_row(
    *,
    country: str,
    audience_type: str,
    target_date: date,
    today_count: int,
    preceding_counts: list[int],
    contributions: list[tuple[str, int]],
) -> dict[str, Any]:
    """Build one country_activity row in the exact shape pipeline.py writes.

    Schema matches ``pipeline.py:600-617`` so ``import_backfill.py`` can
    upsert via the existing ``db.upsert_country_activity_batch()`` unchanged.
    """
    baseline = calculate_baseline(preceding_counts)
    deviation = calculate_deviation(today_count, baseline)

    top_outlets = sorted(contributions, key=lambda x: x[1], reverse=True)[:10]

    return {
        "country": country,
        "date": target_date.isoformat(),
        "audience_type": audience_type,
        "today_count": deviation.today_count,
        "baseline_mean": deviation.baseline_mean,
        "baseline_std": deviation.baseline_std,
        "deviation_ratio": deviation.ratio,
        "z_score": deviation.z_score,
        "level": deviation.level,
        "confidence": deviation.confidence,
        # Cold start flag: true if we don't yet have 7 days of preceding data.
        # import_backfill.py runs a one-time UPDATE after successful import to
        # flip all historical rows to cold_start=false so the frontend banner
        # shows "Live Intelligence Data" instead of "Baseline calibrating".
        "cold_start": baseline.days_sampled < MIN_SAMPLE_DAYS,
        # TimelineVolRaw doesn't give theme data. A5 enrichment fills these in
        # for the recent 30-day window using the existing ArtList pipeline.
        "top_themes": {},
        "top_outlets": [{"domain": d, "count": c} for d, c in top_outlets],
    }


def run_backfill(
    *,
    start_date: date,
    end_date: date,
    outlets: list[OutletRecord] | None = None,
    timeline_client: TimelineClient | None = None,
    baseline_window_days: int = BASELINE_WINDOW_DAYS,
    resume_from: str | None = None,
    verbose: bool = False,
) -> BackfillResult:
    """Execute a historical backfill over ``[start_date, end_date]``.

    Args:
        start_date: inclusive first day of the backfill window.
        end_date: inclusive last day of the backfill window.
        outlets: list of OutletRecords to query. Defaults to ``get_all_outlets()``.
        timeline_client: injectable timeline query function for tests.
            Defaults to :func:`query_domain_timeline`.
        baseline_window_days: rolling baseline window size (30 by default).
        resume_from: optional outlet domain — skip all outlets alphabetically
            STRICTLY BEFORE this one. Used for resuming a crashed run without
            re-querying completed outlets.
        verbose: if True, log every outlet's result. If False, log every 10th.

    Returns:
        :class:`BackfillResult` ready for JSON export and Supabase import.

    Raises:
        ValueError: if start_date > end_date.
    """
    if start_date > end_date:
        raise ValueError(
            f"start_date {start_date} must be <= end_date {end_date}"
        )

    if outlets is None:
        outlets = get_all_outlets()
    if timeline_client is None:
        timeline_client = query_domain_timeline

    all_dates = _date_range(start_date, end_date)
    stats = BackfillStats(days_covered=len(all_dates))
    failures: list[tuple[str, str]] = []

    # Resume filtering (alphabetical by domain)
    outlets_to_query, skipped = _filter_outlets_for_resume(outlets, resume_from)
    stats.outlets_skipped = skipped
    logger.info(
        "Backfill starting: window=%s..%s outlets=%d (skipped=%d) days=%d",
        start_date,
        end_date,
        len(outlets_to_query),
        skipped,
        len(all_dates),
    )

    # 1. Query every outlet for daily volumes
    per_outlet_daily = _query_outlets(
        outlets_to_query,
        start_date=start_date,
        end_date=end_date,
        timeline_client=timeline_client,
        stats=stats,
        failures=failures,
        verbose=verbose,
    )

    # 2. Aggregate into per-bucket time series and contribution tracking
    series, contributions = _aggregate_per_bucket(outlets_to_query, per_outlet_daily)

    # Registered buckets come from the outlet list, not series.keys(), so we
    # emit rows even for buckets where every outlet reported zero.
    registered_buckets = _registered_buckets(outlets_to_query)

    # 3. Emit country_activity rows for every (bucket, date) combination
    activity_rows: list[dict[str, Any]] = []
    for bucket in sorted(registered_buckets):
        country, audience_type = bucket
        daily_counts = series.get(bucket, {})
        for target_date in all_dates:
            today_count = daily_counts.get(target_date, 0)
            preceding_counts = _build_preceding_counts(
                daily_counts,
                target_date=target_date,
                backfill_start=start_date,
                window_days=baseline_window_days,
            )
            contribs = contributions.get((country, audience_type, target_date), [])
            row = _build_activity_row(
                country=country,
                audience_type=audience_type,
                target_date=target_date,
                today_count=today_count,
                preceding_counts=preceding_counts,
                contributions=contribs,
            )
            activity_rows.append(row)
            stats.country_activity_rows += 1

    # 4. Flatten raw outlet counts for the optional audit trail in output JSON
    raw_outlet_daily_counts: dict[tuple[str, date], int] = {}
    for domain, daily in per_outlet_daily.items():
        for day, count in daily.items():
            raw_outlet_daily_counts[(domain, day)] = count

    logger.info(
        "Backfill complete: %d outlets succeeded (%d empty), %d failed, %d rows emitted",
        stats.outlets_succeeded,
        stats.outlets_empty,
        stats.outlets_failed,
        stats.country_activity_rows,
    )

    return BackfillResult(
        stats=stats,
        country_activity=activity_rows,
        raw_outlet_daily_counts=raw_outlet_daily_counts,
        failures=failures,
    )


__all__ = [
    "BackfillStats",
    "BackfillResult",
    "run_backfill",
    "TimelineClient",
]

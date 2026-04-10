"""GDELT DOC 2.0 TimelineVolRaw query wrapper.

Sibling of ``gdelt_client.py``. Where that module handles ArtList mode (returns
individual article records, capped at 250 per query), this module handles
TimelineVolRaw mode (returns per-day article counts, no 250-cap).

The whole reason this exists: historical backfill. We want to pull 15 months of
daily publication volumes per outlet, which would require thousands of ArtList
queries to stitch together. TimelineVolRaw returns the entire date range in a
single query because it aggregates server-side.

References:
    https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
    https://github.com/alex9smith/gdelt-doc-api

Example:
    >>> from datetime import date
    >>> result = query_domain_timeline(
    ...     "xinhuanet.com",
    ...     start_date=date(2025, 1, 1),
    ...     end_date=date(2025, 6, 30),
    ... )
    >>> len(result.rows)  # ~180 daily rows
    181
    >>> result.total_volume  # sum across all days
    24719

Key design decisions:

  - Use ``domain_exact`` NOT ``domain``. Substring matches would pick up
    lookalike domains (e.g. domain="xinhuanet.com" would match
    "not-xinhuanet.com"). Since our outlet database uses canonical domains,
    exact match is what we want.

  - Empty DataFrame is NOT an error. An outlet that produced zero articles on
    a given day is a valid result; callers persist it as a zero count. This
    matches the aggregation semantics of the backfill module.

  - Discard the ``All Articles`` column. It drifts over time as GDELT adds /
    removes crawl sources, which would contaminate year-over-year ratios and
    make the baseline meaningless. Only ``Volume Raw`` is durable.

  - Rate-limit between queries via monotonic clock. ``gdeltdoc`` itself does
    NOT handle rate limits — we must. Safe pace per the GDELT DOC 2.0 API
    notes is ~1 query per 2-3 seconds.

  - Reuse ``gdelt_client._execute_with_retry`` and ``_new_doc_client`` for
    consistent backoff and HTTP timeout behavior across the two clients.

Phase A (historical backfill) introduces this module. Not called by the live
hourly pipeline; only used by ``scripts/run_backfill.py``.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

import pandas as pd

from .gdelt_client import (
    DEFAULT_BACKOFF_BASE,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_MAX_RETRIES,
    _execute_with_retry,
    _new_doc_client,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Safe pace for timeline queries. GDELT's unpublished rate limit appears to
# kick in around 1 query per second; 2.5s gives comfortable headroom even when
# multiple scripts are running. Each outlet in a 15-month backfill needs 1-3
# queries total, so at 2.5s the full 172-outlet run completes in ~7 minutes.
DEFAULT_TIMELINE_RATE_LIMIT_SECONDS = 2.5

# The DataFrame columns returned by gdeltdoc.timeline_search("timelinevolraw").
# Documented at https://github.com/alex9smith/gdelt-doc-api#timeline-queries
TIMELINE_DATETIME_COL = "datetime"
# gdeltdoc renamed the volume column between 1.10.3 ("Volume Raw") and
# 1.12.0 ("Article Count"). We accept either — whichever shows up first in
# ``df.columns`` wins. If neither is present, the parser logs a warning
# and returns empty (matching the "GDELT schema drift" defensive posture).
#
# Empirical evidence: the first production backfill run on 2026-04-10 hit
# gdeltdoc 1.12.0 and saw every outlet's DataFrame returning
# ['All Articles', 'Article Count', 'datetime'] instead of the documented
# ['All Articles', 'Volume Raw', 'datetime']. The library's release notes
# didn't flag the rename.
TIMELINE_VOLUME_COLS: tuple[str, ...] = ("Article Count", "Volume Raw")


@dataclass
class TimelineRow:
    """One day of volume data for one outlet."""

    date: date
    volume_raw: int
    domain: str


@dataclass
class TimelineResult:
    """Result of a single timeline query covering ``[start_date, end_date]``.

    An empty ``rows`` list is a valid result (the outlet produced zero
    articles over the entire window, or GDELT has no coverage of that outlet
    in that period). Callers should NOT treat empty results as errors.
    """

    rows: list[TimelineRow]
    domain: str
    start_date: date
    end_date: date
    duration_seconds: float
    retries: int = 0

    @property
    def is_empty(self) -> bool:
        return not self.rows

    @property
    def total_volume(self) -> int:
        return sum(r.volume_raw for r in self.rows)

    def __len__(self) -> int:
        return len(self.rows)


def _format_gdelt_date(d: date) -> str:
    """Format a ``date`` for ``gdeltdoc.Filters`` start_date / end_date.

    gdeltdoc accepts ``YYYY-MM-DD`` strings.
    """
    return d.strftime("%Y-%m-%d")


def _build_timeline_filters(domain: str, start_date: date, end_date: date):
    """Build a ``gdeltdoc.Filters`` object for a timeline query.

    Imported lazily so unit tests can stub without the package installed.

    Uses ``domain_exact`` to avoid lookalike substring matches — a crucial
    distinction for outlets whose canonical domain is a substring of another
    outlet or a spoof. Per the Plan agent's research, gdeltdoc>=1.10.1
    correctly honors ``domain_exact``; earlier versions had a filter bug.
    """
    try:
        from gdeltdoc import Filters
    except ImportError as exc:  # pragma: no cover — only in dev env without dep
        raise ImportError(
            "gdeltdoc is not installed. Install with `pip install gdeltdoc>=1.10.3`."
        ) from exc

    return Filters(
        start_date=_format_gdelt_date(start_date),
        end_date=_format_gdelt_date(end_date),
        domain_exact=domain,
    )


def _parse_timeline_dataframe(df: pd.DataFrame, domain: str) -> list[TimelineRow]:
    """Convert a gdeltdoc TimelineVolRaw DataFrame into ``TimelineRow`` records.

    Expected DataFrame columns:

        datetime        pandas.Timestamp — one row per day
        volume          int — raw article count on that day. Column name is
                        "Article Count" in gdeltdoc 1.12+ or "Volume Raw" in
                        1.10.3 — we accept either. See TIMELINE_VOLUME_COLS.
        All Articles    int — total matching articles (IGNORED — drifts over time)

    Empty DataFrame is NOT an error. It's a valid "no activity" signal.
    Returns an empty list if the DataFrame is missing required columns
    (logged as a warning for operator visibility).
    """
    if df is None or df.empty:
        return []

    # Datetime column is stable across gdeltdoc versions.
    if TIMELINE_DATETIME_COL not in df.columns:
        logger.warning(
            "TimelineVolRaw response for domain=%s missing datetime column. "
            "Got: %s",
            domain,
            sorted(df.columns),
        )
        return []

    # Volume column name changed between gdeltdoc 1.10.3 and 1.12.0.
    # Accept either. Whichever shows up first in TIMELINE_VOLUME_COLS wins.
    volume_col: str | None = None
    for candidate in TIMELINE_VOLUME_COLS:
        if candidate in df.columns:
            volume_col = candidate
            break
    if volume_col is None:
        logger.warning(
            "TimelineVolRaw response for domain=%s missing any recognized "
            "volume column (tried %s). Got: %s",
            domain,
            list(TIMELINE_VOLUME_COLS),
            sorted(df.columns),
        )
        return []

    rows: list[TimelineRow] = []
    for _, r in df.iterrows():
        raw_dt = r[TIMELINE_DATETIME_COL]
        day = _coerce_to_date(raw_dt)
        if day is None:
            logger.debug(
                "Skipping unparseable datetime in timeline row: %r (type=%s)",
                raw_dt,
                type(raw_dt).__name__,
            )
            continue

        try:
            volume = int(r[volume_col])
        except (ValueError, TypeError):
            logger.debug(
                "Skipping unparseable volume in timeline row for %s: %r",
                domain,
                r[volume_col],
            )
            continue

        rows.append(TimelineRow(date=day, volume_raw=volume, domain=domain))

    return rows


def _coerce_to_date(raw: object) -> date | None:
    """Best-effort coercion of whatever gdeltdoc gives us into a ``date``.

    gdeltdoc emits pandas Timestamps in modern versions, but handle str /
    datetime / date gracefully in case the format drifts or tests pass
    synthetic data.
    """
    if isinstance(raw, pd.Timestamp):
        return raw.date()
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw).date()
        except ValueError:
            try:
                return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").date()
            except ValueError:
                return None
    return None


def query_domain_timeline(
    domain: str,
    start_date: date,
    end_date: date,
    *,
    rate_limit_seconds: float = DEFAULT_TIMELINE_RATE_LIMIT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
    http_timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> TimelineResult:
    """Query GDELT TimelineVolRaw for ``domain`` over ``[start_date, end_date]``.

    Args:
        domain: exact outlet domain, e.g. ``"xinhuanet.com"``. Uses
            ``domain_exact`` filter (substring matches are NOT used — a
            crucial distinction for lookalike-prone domains).
        start_date: inclusive start of the window.
        end_date: inclusive end of the window.
        rate_limit_seconds: sleep this long before issuing the query, to pace
            against GDELT's unpublished rate limit.
        max_retries: retries on transient errors (429s, timeouts, etc.).
        backoff_base: exponential backoff base in seconds.
        http_timeout: bounded HTTP timeout to prevent hung sockets from
            starving the caller's time budget.

    Returns:
        :class:`TimelineResult` containing per-day rows. Empty rows list is a
        valid result (outlet produced zero articles across the window); it is
        NOT an error.

    Raises:
        ValueError: if ``start_date > end_date``.
    """
    if start_date > end_date:
        raise ValueError(
            f"start_date {start_date} must be <= end_date {end_date} for domain={domain}"
        )

    description = f"timeline domain={domain} {start_date}..{end_date}"

    # Rate-limit BEFORE each query. Monotonic clock so retries don't starve.
    if rate_limit_seconds > 0:
        time.sleep(rate_limit_seconds)

    start_time = time.monotonic()

    def _do() -> pd.DataFrame:
        try:
            from gdeltdoc import GdeltDoc  # noqa: F401 — used via _new_doc_client
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "gdeltdoc is not installed. Install with `pip install gdeltdoc>=1.10.3`."
            ) from exc

        # Reuse the HTTP-timeout-patched client factory from gdelt_client.
        client = _new_doc_client(timeout=http_timeout)
        filters = _build_timeline_filters(
            domain=domain,
            start_date=start_date,
            end_date=end_date,
        )
        return client.timeline_search("timelinevolraw", filters)

    df, retries = _execute_with_retry(
        _do,
        description=description,
        max_retries=max_retries,
        backoff_base=backoff_base,
    )
    rows = _parse_timeline_dataframe(df, domain=domain)
    duration = time.monotonic() - start_time

    logger.info(
        "[%s] returned %d daily rows (total_volume=%d) in %.2fs (retries=%d)",
        description,
        len(rows),
        sum(r.volume_raw for r in rows),
        duration,
        retries,
    )

    return TimelineResult(
        rows=rows,
        domain=domain,
        start_date=start_date,
        end_date=end_date,
        duration_seconds=duration,
        retries=retries,
    )


__all__ = [
    "TimelineRow",
    "TimelineResult",
    "query_domain_timeline",
    "DEFAULT_TIMELINE_RATE_LIMIT_SECONDS",
    "TIMELINE_DATETIME_COL",
    "TIMELINE_VOLUME_COLS",
]

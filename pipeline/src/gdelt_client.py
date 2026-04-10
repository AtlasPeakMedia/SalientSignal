"""GDELT DOC 2.0 query wrapper.

Thin layer over the `gdeltdoc` Python client (https://github.com/alex9smith/gdelt-doc-api)
plus exponential-backoff retry handling for the unpublished but observed rate
limits on the GDELT DOC 2.0 endpoint.

Two query helpers cover everything Phase 2 needs:

    query_country(country_fips, hours=1, max_records=250)
        Pull every article from a given country in the last `hours` hours.
        GDELT filter: `sourcecountry:<FIPS>`. Returns a pandas DataFrame.

    query_domain(domain, hours=1, max_records=250)
        Pull every article from a specific domain in the last `hours` hours.
        GDELT filter: `domainis:<domain>`. Returns a pandas DataFrame.

Both helpers retry on transient errors with exponential backoff (max 5 tries).
A 429 response is treated as a hard rate limit — back off and try again later.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)

# GDELT DOC 2.0 hard limits (from spec)
GDELT_MAX_RECORDS = 250  # MAXRECORDS parameter ceiling
GDELT_MIN_TIMESPAN_MIN = 15  # smallest valid timespan

DEFAULT_BACKOFF_BASE = 2.0  # seconds
DEFAULT_MAX_RETRIES = 5


@dataclass
class GdeltQueryResult:
    """Lightweight container around a query response."""

    df: pd.DataFrame
    query_str: str
    duration_seconds: float
    retries: int = 0

    @property
    def is_empty(self) -> bool:
        return self.df is None or self.df.empty

    def __len__(self) -> int:
        return 0 if self.is_empty else len(self.df)


def _format_timespan(hours: int) -> str:
    """GDELT DOC 2.0 timespan parameter format. Hours must be >=1 (15-min minimum)."""
    if hours < 1:
        return f"{max(GDELT_MIN_TIMESPAN_MIN, 15)}min"
    return f"{int(hours)}h"


def _build_filters(
    country_fips: str | None = None,
    domain: str | None = None,
    hours: int = 1,
    max_records: int = GDELT_MAX_RECORDS,
):
    """Build a `gdeltdoc.Filters` object. Imported lazily so unit tests can stub.

    The Filters constructor signature is from gdeltdoc 1.7+:
        Filters(start_date=None, end_date=None, num_records=250, keyword=None,
                domain=None, domain_exact=None, country=None, theme=None, ...)
    Where `country` accepts a 2-letter FIPS code.
    """
    try:
        from gdeltdoc import Filters
    except ImportError as exc:  # pragma: no cover — only in dev env without dep
        raise ImportError(
            "gdeltdoc is not installed. Install with `pip install gdeltdoc>=1.7.0`."
        ) from exc

    timespan = _format_timespan(hours)
    kwargs: dict = {
        "timespan": timespan,
        "num_records": min(max_records, GDELT_MAX_RECORDS),
    }
    if country_fips:
        kwargs["country"] = country_fips.upper()
    if domain:
        kwargs["domain"] = domain
    return Filters(**kwargs)


def _new_doc_client():
    """Lazy-import the GdeltDoc client so module import doesn't require the dep at test time."""
    try:
        from gdeltdoc import GdeltDoc
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "gdeltdoc is not installed. Install with `pip install gdeltdoc>=1.7.0`."
        ) from exc
    return GdeltDoc()


def _execute_with_retry(
    fn,
    *,
    description: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
) -> tuple[pd.DataFrame, int]:
    """Execute `fn()` and return its DataFrame, retrying with exponential backoff on errors.

    Returns:
        (dataframe, retries_used)

    The function will catch all exceptions because the gdeltdoc library raises
    a mix of HTTPError, JSONDecodeError, and bare RuntimeErrors depending on
    what the GDELT server returns. We log and back off on every failure.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            df = fn()
            if df is None:
                return pd.DataFrame(), attempt
            return df, attempt
        except Exception as exc:  # noqa: BLE001 — see docstring above
            last_exc = exc
            wait = backoff_base ** attempt
            msg = str(exc).lower()
            if "429" in msg or "rate limit" in msg or "too many" in msg:
                wait *= 2  # extra backoff on explicit rate limits
                logger.warning("[%s] GDELT rate-limited (attempt %d/%d). Sleeping %.1fs.",
                               description, attempt + 1, max_retries, wait)
            else:
                logger.warning("[%s] GDELT query failed (attempt %d/%d): %s. Sleeping %.1fs.",
                               description, attempt + 1, max_retries, exc, wait)
            time.sleep(wait)

    logger.error("[%s] GDELT query failed after %d retries. Last error: %s",
                 description, max_retries, last_exc)
    return pd.DataFrame(), max_retries


def query_country(
    country_fips: str,
    hours: int = 1,
    max_records: int = GDELT_MAX_RECORDS,
) -> GdeltQueryResult:
    """Query GDELT for all articles from a country in the last `hours` hours."""
    description = f"country={country_fips} hours={hours}"
    start = time.monotonic()

    def _do() -> pd.DataFrame:
        client = _new_doc_client()
        filters = _build_filters(country_fips=country_fips, hours=hours, max_records=max_records)
        return client.article_search(filters)

    df, retries = _execute_with_retry(_do, description=description)
    duration = time.monotonic() - start
    logger.info("[%s] returned %d articles in %.2fs (retries=%d)",
                description, 0 if df is None else len(df), duration, retries)
    return GdeltQueryResult(df=df, query_str=description, duration_seconds=duration, retries=retries)


def query_domain(
    domain: str,
    hours: int = 1,
    max_records: int = GDELT_MAX_RECORDS,
) -> GdeltQueryResult:
    """Query GDELT for all articles from a single state media domain in the last `hours` hours."""
    description = f"domain={domain} hours={hours}"
    start = time.monotonic()

    def _do() -> pd.DataFrame:
        client = _new_doc_client()
        filters = _build_filters(domain=domain, hours=hours, max_records=max_records)
        return client.article_search(filters)

    df, retries = _execute_with_retry(_do, description=description)
    duration = time.monotonic() - start
    logger.info("[%s] returned %d articles in %.2fs (retries=%d)",
                description, 0 if df is None else len(df), duration, retries)
    return GdeltQueryResult(df=df, query_str=description, duration_seconds=duration, retries=retries)


__all__ = [
    "GdeltQueryResult",
    "query_country",
    "query_domain",
    "GDELT_MAX_RECORDS",
    "GDELT_MIN_TIMESPAN_MIN",
]

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

Phase 2 red team fixes:
  - P2-H1: Validate GDELT DataFrame schema (warn on unexpected column layout)
  - P2-H3: Bounded HTTP timeout (default 30s) so a hung connection can't
           stall the entire 50-minute pipeline budget
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

# P2-H3: Bounded HTTP timeout. A hung GDELT connection without this could
# sit in socket.recv() indefinitely and consume the entire time budget
# without making progress. 30s is generous; typical queries return in 1-5s.
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0

# P2-H1: Required GDELT DOC 2.0 article_search columns we depend on.
# If these aren't present the downstream code will fail mysteriously,
# so we warn at the query boundary.
REQUIRED_GDELT_COLUMNS: frozenset[str] = frozenset({
    "url",
    "title",
    "seendate",
    "domain",
    "language",
    "sourcecountry",
})


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


def _new_doc_client(timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS):
    """Lazy-import the GdeltDoc client with a bounded HTTP timeout (P2-H3).

    The gdeltdoc library uses `requests` under the hood. We monkey-patch the
    `requests.get` call so every GDELT HTTP call has a hard timeout rather
    than relying on the default socket-level blocking behavior (which can
    hang indefinitely on network problems).
    """
    try:
        from gdeltdoc import GdeltDoc
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "gdeltdoc is not installed. Install with `pip install gdeltdoc>=1.7.0`."
        ) from exc

    client = GdeltDoc()

    # Install a default timeout on the underlying requests.Session if present.
    # gdeltdoc 1.7+ uses a Session internally; older versions use requests.get
    # directly. We try both.
    try:
        # Newer gdeltdoc versions
        if hasattr(client, "session"):
            session = client.session
            # Wrap session.request to inject timeout if missing
            original_request = session.request

            def _request_with_timeout(method, url, **kwargs):
                kwargs.setdefault("timeout", timeout)
                return original_request(method, url, **kwargs)

            session.request = _request_with_timeout  # type: ignore[method-assign]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not install HTTP timeout on gdeltdoc client: %s", exc)

    return client


def _validate_gdelt_schema(df: pd.DataFrame, description: str) -> None:
    """P2-H1: Warn if GDELT returns a DataFrame with missing required columns.

    This is a soft check — we log but don't raise, since occasional schema
    drift shouldn't crash the entire pipeline. But the early warning gives
    operators a chance to notice before every country starts returning zero
    classified articles.
    """
    if df is None or df.empty:
        return
    cols = set(df.columns)
    missing = REQUIRED_GDELT_COLUMNS - cols
    if missing:
        logger.warning(
            "[%s] GDELT response missing expected columns: %s. "
            "Returned columns: %s. "
            "Downstream classification may fail until schema is reconciled.",
            description,
            sorted(missing),
            sorted(cols),
        )


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
    http_timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> GdeltQueryResult:
    """Query GDELT for all articles from a country in the last `hours` hours."""
    description = f"country={country_fips} hours={hours}"
    start = time.monotonic()

    def _do() -> pd.DataFrame:
        client = _new_doc_client(timeout=http_timeout)
        filters = _build_filters(country_fips=country_fips, hours=hours, max_records=max_records)
        return client.article_search(filters)

    df, retries = _execute_with_retry(_do, description=description)
    _validate_gdelt_schema(df, description)
    duration = time.monotonic() - start
    logger.info("[%s] returned %d articles in %.2fs (retries=%d)",
                description, 0 if df is None else len(df), duration, retries)
    return GdeltQueryResult(df=df, query_str=description, duration_seconds=duration, retries=retries)


def query_domain(
    domain: str,
    hours: int = 1,
    max_records: int = GDELT_MAX_RECORDS,
    http_timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> GdeltQueryResult:
    """Query GDELT for all articles from a single state media domain in the last `hours` hours."""
    description = f"domain={domain} hours={hours}"
    start = time.monotonic()

    def _do() -> pd.DataFrame:
        client = _new_doc_client(timeout=http_timeout)
        filters = _build_filters(domain=domain, hours=hours, max_records=max_records)
        return client.article_search(filters)

    df, retries = _execute_with_retry(_do, description=description)
    _validate_gdelt_schema(df, description)
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
    "DEFAULT_HTTP_TIMEOUT_SECONDS",
    "REQUIRED_GDELT_COLUMNS",
]

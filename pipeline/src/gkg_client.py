"""GDELT GKG 2.0 bulk file client.

The GDELT DOC 2.0 API (https://api.gdeltproject.org/api/v2/doc/doc) does NOT
expose per-article theme data. ArtList mode returns only url, title, seendate,
domain, language, sourcecountry — no themes, no entities, no tone. And the
documented "wordcloud" modes are all image-based (`wordcloudimagetags`,
`wordcloudimagewebtags`), not text themes. This was a late-night architectural
finding on 2026-04-10: our previous `themes.py::extract_themes()` function
looked for fields that the DOC 2.0 API never populates, so every article in
Supabase had `gdelt_themes=[]` (silent no-op).

The real theme data lives in the GKG 2.0 bulk CSV files, published every
15 minutes to a separate Google Cloud Storage CDN:

    http://data.gdeltproject.org/gdeltv2/YYYYMMDDHHMMSS.gkg.csv.zip

Each file contains ~1,000-2,000 rows, one per article GDELT crawled in that
15-min window, with full theme codes in the `V1Themes` and `V2Themes` columns,
plus locations, persons, organizations, tone (V2Tone), and GCAM scores.

This module is the low-level client. It downloads one 15-min file, unzips
it in memory, parses the tab-delimited CSV, and returns only rows matching
our monitored domain set. Higher layers (theme_aggregator.py,
run_gkg_backfill.py) call this repeatedly for a date range and aggregate
the results.

Separate CDN note: `data.gdeltproject.org` is a separate endpoint from
`api.gdeltproject.org`. DOC API rate limits do NOT apply here. You can fetch
thousands of GKG files in parallel without hitting the 429s that plague the
DOC API after heavy backfill runs.

CSV schema (GDELT GKG 2.0, 27 tab-delimited fields):
    0  GKGRECORDID         e.g. "20260409120000-0"
    1  V2.1DATE            YYYYMMDDHHMMSS
    2  V2SourceCollectionIdentifier  1 = WEB
    3  V2SourceCommonName  the domain (e.g. "tass.ru")
    4  V2DocumentIdentifier  full URL
    5  V1Counts            type#count#object;...
    6  V2.1Counts          same with charOffset
    7  V1Themes            SEMICOLON-separated theme codes
    8  V2EnhancedThemes    with charOffset
    9  V1Locations         locations with FIPS/ISO codes
    10 V2EnhancedLocations
    11 V1Persons
    12 V2EnhancedPersons
    13 V1Organizations
    14 V2EnhancedOrganizations
    15 V1.5Tone            average tone
    16 V2.1EnhancedDates
    17 V2GCAM              huge bag of sentiment words
    18 V2.1SharingImage
    19 V2.1RelatedImages
    20 V2.1SocialImageEmbeds
    21 V2.1SocialVideoEmbeds
    22 V2.1Quotations
    23 V2.1AllNames
    24 V2.1Amounts
    25 V2.1TranslationInfo
    26 V2ExtrasXML         <PAGE_LINKS>...</PAGE_LINKS><PAGE_TITLE>...</PAGE_TITLE>

Public surface:

    GkgRow                  — a matched row (domain, url, themes, title, ...)
    build_masterfile_url()  — stringify a 15-min timestamp to a download URL
    fetch_gkg_file()        — download + filter one 15-min slice
    parse_gkg_line()        — parse one CSV line into a GkgRow (public for tests)
"""
from __future__ import annotations

import io
import logging
import re
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

logger = logging.getLogger(__name__)

# GDELT GKG 2.0 bulk CDN base. Files are published every 15 minutes.
GKG_BULK_BASE_URL = "http://data.gdeltproject.org/gdeltv2"

# 15-min cadence: files at :00, :15, :30, :45 past each hour (UTC).
VALID_GKG_MINUTES = (0, 15, 30, 45)

# How many CSV columns we expect. GKG 2.0 schema has 27 columns (0-26 indexed).
# Files with fewer columns are either malformed or from an older GKG version;
# we skip them and log a warning rather than crash.
GKG_V2_MIN_COLUMNS = 17  # We need at least through V2.1EnhancedDates (index 16)

# HTTP timeout for a single file download in seconds. GKG CDN is Google Cloud
# Storage which is very fast, so this is generous.
DEFAULT_HTTP_TIMEOUT_SECONDS = 60.0

# Retry budget per file download.
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 2.0

# Regex to pull the title out of the V2ExtrasXML column (the last field).
# Example: "<PAGE_LINKS>...</PAGE_LINKS><PAGE_TITLE>Kengo Kuma Wins...</PAGE_TITLE>"
PAGE_TITLE_RE = re.compile(r"<PAGE_TITLE>([^<]*)</PAGE_TITLE>", re.IGNORECASE)


@dataclass
class GkgRow:
    """One article from a GKG 2.0 file, after domain filtering.

    Only the fields we actually need for the theme dashboard. We deliberately
    drop the ~80% of each row we don't use (GCAM, V2.1Amounts, all the
    enhanced-with-charoffset columns) to keep memory footprint small during
    the 15-month backfill. If we ever need those later we parse them at
    ingest time, not store them.

    Attributes:
        record_id: The GKGRECORDID (useful for dedup — GDELT sometimes emits
            the same row across adjacent 15-min files).
        date: The article's extraction datetime in UTC. Stored as a timezone-
            aware datetime so the aggregator can bucket by week/month without
            timezone guessing.
        domain: The normalized lowercase domain (post subdomain walk-up to
            the registered parent). E.g. "french.xinhuanet.com" -> "xinhuanet.com".
        raw_domain: What GDELT actually returned before walk-up. Useful for
            per-subdomain reporting if we ever want language-specific rollups.
        url: The full article URL.
        title: PAGE_TITLE extracted from the V2ExtrasXML field. May be empty.
        themes_v1: Sorted list of unique V1 theme codes (semicolon-separated
            in the source, deduped here). These are the plain theme tags like
            "TAX_FNCACT_PRESIDENT", "ARMEDCONFLICT", "WB_694_BROADCAST_AND_MEDIA".
        tone: Average article tone (V1.5Tone average field). Floats -10..+10,
            negative is more negative coverage. Can be None if the row has
            no parseable tone.
    """

    record_id: str
    date: datetime
    domain: str
    raw_domain: str
    url: str
    title: str
    themes_v1: list[str]
    tone: float | None = None


# ----------------------------------------------------------------------------
# URL building
# ----------------------------------------------------------------------------
def build_masterfile_url(slice_time: datetime) -> str:
    """Stringify a 15-min UTC slice into the GKG 2.0 download URL.

    Args:
        slice_time: A timezone-aware datetime whose minute MUST be one of
            0, 15, 30, 45. GKG files are not published at arbitrary minutes.

    Returns:
        The full GKG download URL.

    Raises:
        ValueError: If the minute is not a valid GKG 15-min boundary, or if
            the datetime is naive (missing tzinfo).

    Examples:
        >>> from datetime import datetime, timezone
        >>> build_masterfile_url(datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc))
        'http://data.gdeltproject.org/gdeltv2/20260409120000.gkg.csv.zip'
    """
    if slice_time.tzinfo is None:
        raise ValueError("slice_time must be timezone-aware (use tzinfo=timezone.utc)")
    if slice_time.minute not in VALID_GKG_MINUTES:
        raise ValueError(
            f"slice_time.minute must be one of {VALID_GKG_MINUTES}, got {slice_time.minute}"
        )
    # Normalize to UTC, then format as YYYYMMDDHHMMSS with zero seconds.
    utc = slice_time.astimezone(timezone.utc)
    stamp = utc.strftime("%Y%m%d%H%M00")
    return f"{GKG_BULK_BASE_URL}/{stamp}.gkg.csv.zip"


def iter_15min_slices(
    start: datetime, end: datetime
) -> Iterable[datetime]:
    """Yield every 15-min slice timestamp between start and end (inclusive).

    Both arguments must be timezone-aware and already aligned to a 15-min
    boundary. Yields a new datetime per 15-min tick from start to end.
    """
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware")
    if start.minute not in VALID_GKG_MINUTES or end.minute not in VALID_GKG_MINUTES:
        raise ValueError("start and end must be on 15-min boundaries")
    current = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    step_seconds = 15 * 60
    while current <= end_utc:
        yield current
        # Advance by 15 minutes (use timestamp arithmetic to avoid DST nonsense)
        current = datetime.fromtimestamp(
            current.timestamp() + step_seconds, tz=timezone.utc
        )


# ----------------------------------------------------------------------------
# CSV parsing
# ----------------------------------------------------------------------------
def _parse_themes_v1(raw: str) -> list[str]:
    """Parse the V1Themes column — semicolon-separated codes with trailing sep.

    Input example: "TAX_FNCACT;ARMEDCONFLICT;TAX_FNCACT_PRESIDENT;"
    Returns: ["ARMEDCONFLICT", "TAX_FNCACT", "TAX_FNCACT_PRESIDENT"]

    Duplicates are collapsed and the output is sorted for deterministic
    aggregation ordering.
    """
    if not raw:
        return []
    parts = {p.strip() for p in raw.split(";") if p.strip()}
    return sorted(parts)


def _parse_tone(raw: str) -> float | None:
    """Parse the V1.5Tone column — comma-separated floats, first is avg tone.

    Format: "avgTone,posScore,negScore,polarity,activityRef,selfRef,wordCount"
    We only want the first value (avgTone).
    """
    if not raw:
        return None
    head = raw.split(",", 1)[0].strip()
    if not head:
        return None
    try:
        return float(head)
    except ValueError:
        return None


def _parse_title(extras_xml: str) -> str:
    """Pull PAGE_TITLE text out of the V2ExtrasXML field."""
    if not extras_xml:
        return ""
    m = PAGE_TITLE_RE.search(extras_xml)
    if not m:
        return ""
    # Unescape common entities the hard way — GDELT's XML escaping is
    # inconsistent, so we just handle the common cases.
    title = m.group(1).strip()
    return (
        title.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )


def _parse_record_date(stamp: str) -> datetime | None:
    """Parse a GKGRECORDID-style YYYYMMDDHHMMSS stamp into a UTC datetime."""
    if not stamp or len(stamp) < 14:
        return None
    try:
        return datetime.strptime(stamp[:14], "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _walk_up_to_registered_domain(
    raw_domain: str, registered: set[str]
) -> str | None:
    """Try the raw domain, then parents (subdomain walk-up), against `registered`.

    This matches the existing pipeline convention: "french.xinhuanet.com"
    resolves to "xinhuanet.com" if only the parent is in outlets.json.

    Args:
        raw_domain: Lowercased domain from GKG.
        registered: The set of monitored domains (also lowercased).

    Returns:
        The matched registered domain, or None if nothing matched.
    """
    if not raw_domain:
        return None
    if raw_domain in registered:
        return raw_domain
    parts = raw_domain.split(".")
    for i in range(1, len(parts)):
        parent = ".".join(parts[i:])
        if parent in registered:
            return parent
    return None


def parse_gkg_line(line: str, registered_domains: set[str]) -> GkgRow | None:
    """Parse one tab-delimited GKG 2.0 row. Return None if not a match.

    Args:
        line: A single line from a gkg.csv file (without trailing newline).
        registered_domains: Set of lowercased domains we care about. Rows
            not matching (via direct match OR subdomain walk-up) return None.

    Returns:
        A GkgRow if this row's domain matches our monitored set, else None.
        Also returns None for malformed rows (fewer than GKG_V2_MIN_COLUMNS
        fields, unparseable date, etc.) — these are logged as debug, not
        raised as exceptions, because a few bad rows in a 15-month backfill
        shouldn't abort the whole run.
    """
    if not line:
        return None
    parts = line.split("\t")
    if len(parts) < GKG_V2_MIN_COLUMNS:
        return None

    raw_domain = parts[3].strip().lower()
    if not raw_domain:
        return None

    matched_domain = _walk_up_to_registered_domain(raw_domain, registered_domains)
    if matched_domain is None:
        return None

    record_id = parts[0].strip()
    date_field = parts[1].strip()
    url = parts[4].strip()
    themes_raw = parts[7] if len(parts) > 7 else ""
    tone_raw = parts[15] if len(parts) > 15 else ""
    extras_xml = parts[26] if len(parts) > 26 else ""

    dt = _parse_record_date(date_field) or _parse_record_date(record_id)
    if dt is None:
        # Can't place this article in time — skip
        logger.debug("Skipping GKG row with unparseable date: %s", record_id)
        return None

    return GkgRow(
        record_id=record_id,
        date=dt,
        domain=matched_domain,
        raw_domain=raw_domain,
        url=url,
        title=_parse_title(extras_xml),
        themes_v1=_parse_themes_v1(themes_raw),
        tone=_parse_tone(tone_raw),
    )


# ----------------------------------------------------------------------------
# File fetching
# ----------------------------------------------------------------------------
@dataclass
class GkgFileResult:
    """Result of processing one 15-min GKG file.

    Attributes:
        slice_time: The 15-min timestamp we requested.
        rows: The matched GkgRow objects (filtered to our monitored domains).
        total_rows_seen: Total row count in the file before filtering.
        matched_rows: Number of rows that matched (== len(rows)).
        retries: Number of retry attempts needed to fetch the file.
        duration_seconds: Wall-clock time spent fetching + parsing.
        skipped: True if the file was 404 or otherwise unavailable. The
            caller can log this and continue — missing files are not fatal
            for historical backfills (GDELT occasionally has gaps).
        error: The string repr of the last error if skipped=True, else None.
    """

    slice_time: datetime
    rows: list[GkgRow] = field(default_factory=list)
    total_rows_seen: int = 0
    matched_rows: int = 0
    retries: int = 0
    duration_seconds: float = 0.0
    skipped: bool = False
    error: str | None = None


def fetch_gkg_file(
    slice_time: datetime,
    registered_domains: set[str],
    *,
    http_timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
    url_fetcher=None,  # Injectable for tests: (url, timeout) -> bytes
) -> GkgFileResult:
    """Download one GKG 15-min file and return rows matching our domains.

    The file is downloaded, unzipped in memory, parsed line-by-line, and
    filtered. Non-matching rows are discarded immediately so memory stays
    low even for the biggest files (~20 MB uncompressed).

    Args:
        slice_time: Timezone-aware UTC datetime on a 15-min boundary.
        registered_domains: Set of lowercased monitored domains for filtering.
        http_timeout: Per-request timeout in seconds.
        max_retries: Number of retry attempts before giving up.
        backoff_base: Exponential backoff base (1s, 2s, 4s, 8s, ...).
        url_fetcher: Optional test injection. If None, uses urllib to hit the
            real GKG CDN. For unit tests pass a callable (url, timeout)->bytes
            that returns a pre-canned zip payload.

    Returns:
        A GkgFileResult. On 404, skipped=True and rows=[] (not an exception,
        because historical gaps are normal).
    """
    start = time.monotonic()
    result = GkgFileResult(slice_time=slice_time)
    url = build_masterfile_url(slice_time)

    fetcher = url_fetcher or _default_url_fetcher

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            raw_bytes = fetcher(url, http_timeout)
            break
        except urllib.error.HTTPError as http_err:
            if http_err.code == 404:
                # Missing files are a normal gap in historical data.
                logger.info("GKG file missing (404): %s", url)
                result.skipped = True
                result.error = "404"
                result.duration_seconds = time.monotonic() - start
                return result
            last_error = http_err
            logger.warning(
                "GKG fetch %s failed (attempt %d/%d): HTTP %s",
                url, attempt + 1, max_retries + 1, http_err.code,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "GKG fetch %s failed (attempt %d/%d): %s",
                url, attempt + 1, max_retries + 1, exc,
            )

        if attempt < max_retries:
            sleep_s = backoff_base ** attempt
            time.sleep(sleep_s)
            result.retries += 1
        else:
            # Out of retries
            result.skipped = True
            result.error = str(last_error) if last_error else "unknown"
            result.duration_seconds = time.monotonic() - start
            return result

    # We have raw zip bytes — unzip and parse
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            names = zf.namelist()
            if not names:
                result.skipped = True
                result.error = "empty zip"
                result.duration_seconds = time.monotonic() - start
                return result
            # GKG zips contain exactly one .csv file with the same basename
            csv_name = names[0]
            with zf.open(csv_name) as f:
                # Read as bytes then decode — GKG uses latin-1 for some rows
                # that would choke utf-8 parsers.
                raw_text = f.read().decode("utf-8", errors="replace")
    except zipfile.BadZipFile as exc:
        logger.warning("GKG file at %s is not a valid zip: %s", url, exc)
        result.skipped = True
        result.error = f"bad zip: {exc}"
        result.duration_seconds = time.monotonic() - start
        return result

    # Parse line-by-line. GKG files don't have a header row.
    for line in raw_text.splitlines():
        result.total_rows_seen += 1
        row = parse_gkg_line(line, registered_domains)
        if row is not None:
            result.rows.append(row)
    result.matched_rows = len(result.rows)
    result.duration_seconds = time.monotonic() - start
    return result


def _default_url_fetcher(url: str, timeout: float) -> bytes:
    """Default urllib fetcher. Extracted so tests can mock it."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SalientSignal/1.0 (+https://salientsignal.com)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


__all__ = [
    "GkgRow",
    "GkgFileResult",
    "GKG_BULK_BASE_URL",
    "VALID_GKG_MINUTES",
    "build_masterfile_url",
    "iter_15min_slices",
    "parse_gkg_line",
    "fetch_gkg_file",
]

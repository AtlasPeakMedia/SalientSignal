"""Aggregate parsed GKG rows into (country, period, audience, theme) buckets.

The SCAME dashboard's core query is "show me the top themes for Country X
during Month Y for Audience Z (DOMESTIC or INTERNATIONAL)". Storing every
matched GKG row individually would be ~757K rows for 15 months of history —
fine for the free tier but wasteful. The dashboard never asks "what was
this one specific article's themes"; it only asks "what were the dominant
themes in this country/period/audience bucket", so we pre-aggregate.

The aggregator produces rows shaped like:

    {
        "country": "TR",
        "audience_type": "INTERNATIONAL",
        "period_type": "monthly",
        "period_start": date(2026, 4, 1),
        "period_end": date(2026, 4, 30),
        "theme": "ARMEDCONFLICT",
        "article_count": 47,
        "share": 0.12,       # 12% of this bucket's articles mentioned ARMEDCONFLICT
        "avg_tone": -4.7,
    }

These feed directly into the `country_theme_monthly` / `country_theme_weekly`
tables. Each (country, audience, period, theme) is one row. Top 50 themes
per bucket are kept after aggregation finishes — the long tail of obscure
themes is discarded to cap storage.

Public surface:

    PeriodType              — Literal["daily", "weekly", "monthly"]
    ThemeBucket             — one (country, period, audience, theme) row
    aggregate_themes()      — turn GkgRows into ThemeBuckets
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Literal

from .gkg_client import GkgRow
from .outlets import get_outlet

logger = logging.getLogger(__name__)

PeriodType = Literal["daily", "weekly", "monthly"]

# The dashboard only needs the top N themes per bucket — the tail is a long
# noisy list of obscure tags and discarding it shrinks storage ~10x. 50 gives
# generous headroom for word clouds (typical word clouds show ~30-40 items)
# while keeping the write volume manageable.
DEFAULT_TOP_N_PER_BUCKET = 50

# Themes appearing in fewer than this many articles in a given bucket are
# treated as noise and never persisted — even if they'd otherwise make the
# top-N cut. This prevents the monthly CN INTERNATIONAL bucket from storing
# "this one obscure B2B theme appeared once in 30 days".
DEFAULT_MIN_ARTICLE_COUNT = 2


@dataclass
class ThemeBucket:
    """One aggregated theme row ready for DB upsert.

    Attributes:
        country: ISO-2 country code. Derived from the outlet's registered
            country — NOT from GKG's location tagging, because GKG locations
            are article subject matter (e.g. a Turkish article about Russia
            would get "RU" locations) and we want the outlet's origin.
        audience_type: DOMESTIC | INTERNATIONAL | DIASPORA — derived from
            the outlet's registered audience.
        period_type: daily | weekly | monthly
        period_start: The inclusive start date of the bucket (UTC).
        period_end: The inclusive end date of the bucket (UTC).
        theme: The GDELT theme code (e.g. "ARMEDCONFLICT").
        article_count: How many articles in this bucket mentioned the theme.
        bucket_total: Total articles in this bucket (used to compute share).
        share: article_count / bucket_total — float in [0, 1].
        avg_tone: Mean V1.5Tone across articles mentioning this theme. May
            be None if no tone data was available.
    """

    country: str
    audience_type: str
    period_type: PeriodType
    period_start: date
    period_end: date
    theme: str
    article_count: int
    bucket_total: int
    share: float
    avg_tone: float | None

    def to_dict(self) -> dict:
        """Emit a dict shaped for the country_theme_* table upsert."""
        return {
            "country": self.country,
            "audience_type": self.audience_type,
            "period_type": self.period_type,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "theme": self.theme,
            "article_count": self.article_count,
            "bucket_total": self.bucket_total,
            "share": round(self.share, 4),
            "avg_tone": round(self.avg_tone, 3) if self.avg_tone is not None else None,
        }


# ----------------------------------------------------------------------------
# Period bucketing
# ----------------------------------------------------------------------------
def _monthly_period(d: date) -> tuple[date, date]:
    """Return (first_day, last_day) of the month containing d."""
    first = date(d.year, d.month, 1)
    if d.month == 12:
        next_first = date(d.year + 1, 1, 1)
    else:
        next_first = date(d.year, d.month + 1, 1)
    last = next_first - timedelta(days=1)
    return first, last


def _weekly_period(d: date) -> tuple[date, date]:
    """Return (Monday, Sunday) of the ISO week containing d.

    We use ISO weeks (Monday=start) because that's what every chart library
    and fiscal calendar assumes, and because it means a single week never
    straddles a month boundary by more than 6 days.
    """
    # isoweekday: Monday=1, Sunday=7
    weekday = d.isoweekday()
    monday = d - timedelta(days=weekday - 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _daily_period(d: date) -> tuple[date, date]:
    return d, d


def _period_key(d: date, period_type: PeriodType) -> tuple[date, date]:
    if period_type == "monthly":
        return _monthly_period(d)
    if period_type == "weekly":
        return _weekly_period(d)
    return _daily_period(d)


# ----------------------------------------------------------------------------
# Aggregation
# ----------------------------------------------------------------------------
@dataclass
class _ThemeCounter:
    """Intra-bucket state during aggregation — not part of the public API."""

    article_count: int = 0
    tone_sum: float = 0.0
    tone_n: int = 0

    def add(self, tone: float | None) -> None:
        self.article_count += 1
        if tone is not None:
            self.tone_sum += tone
            self.tone_n += 1

    @property
    def avg_tone(self) -> float | None:
        if self.tone_n == 0:
            return None
        return self.tone_sum / self.tone_n


@dataclass
class _BucketState:
    """All per-theme counters for one (country, audience, period) bucket."""

    total_articles: int = 0
    themes: dict[str, _ThemeCounter] = field(default_factory=dict)


def aggregate_themes(
    rows: Iterable[GkgRow],
    *,
    period_type: PeriodType = "monthly",
    top_n: int = DEFAULT_TOP_N_PER_BUCKET,
    min_article_count: int = DEFAULT_MIN_ARTICLE_COUNT,
) -> list[ThemeBucket]:
    """Aggregate an iterable of GkgRows into per-bucket theme rollups.

    Algorithm:
      1. Deduplicate by (domain, url) — GDELT emits the same article across
         adjacent 15-min files sometimes, and the dashboard should count
         each article once per bucket.
      2. For each surviving row, look up its outlet to get country +
         audience_type. Rows for domains not in outlets.json are dropped
         (shouldn't happen because gkg_client already filters upstream,
         but defense in depth).
      3. Compute the period bucket ((country, audience, period_start)).
      4. For each theme on the row, increment the theme counter and track
         tone.
      5. After all rows are processed, emit the top N themes per bucket,
         filtering by `min_article_count` to drop noise.

    The function is pure and deterministic: same input rows always produce
    the same output, with themes sorted by (article_count desc, theme asc)
    for stable tie-breaking. This makes it safe to unit test.

    Args:
        rows: An iterable of GkgRow objects from gkg_client.
        period_type: "monthly" | "weekly" | "daily" bucket granularity.
        top_n: Keep at most this many themes per bucket. The rest are dropped.
        min_article_count: Drop themes with fewer than this many mentions
            even if they'd otherwise make the top-N cut.

    Returns:
        A list of ThemeBucket rows, sorted by (country, audience, period_start,
        rank) for deterministic output.
    """
    # Step 1: dedup by (domain, url)
    seen_urls: set[tuple[str, str]] = set()
    rows_to_process: list[GkgRow] = []
    for row in rows:
        key = (row.domain, row.url)
        if key in seen_urls:
            continue
        seen_urls.add(key)
        rows_to_process.append(row)

    logger.info(
        "aggregate_themes: %d rows after dedup (period_type=%s)",
        len(rows_to_process), period_type,
    )

    # Step 2 + 3 + 4: bucket + count
    buckets: dict[tuple[str, str, date, date], _BucketState] = defaultdict(_BucketState)

    for row in rows_to_process:
        outlet = get_outlet(row.domain)
        if outlet is None:
            # Shouldn't happen because gkg_client filters to registered
            # domains, but be defensive.
            continue
        country = outlet.country
        audience = outlet.audience_type
        # Convert the UTC datetime to a plain date for bucket keying
        row_date = row.date.astimezone(timezone.utc).date()
        period_start, period_end = _period_key(row_date, period_type)
        key = (country, audience, period_start, period_end)

        state = buckets[key]
        state.total_articles += 1
        # Each row's themes contribute to its bucket. Themes are already
        # deduped-within-row by parse_gkg_line, so no double-counting.
        for theme in row.themes_v1:
            counter = state.themes.get(theme)
            if counter is None:
                counter = _ThemeCounter()
                state.themes[theme] = counter
            counter.add(row.tone)

    # Step 5: emit top-N per bucket
    output: list[ThemeBucket] = []
    for (country, audience, period_start, period_end), state in buckets.items():
        # Rank themes by (article_count desc, theme asc)
        ranked = sorted(
            state.themes.items(),
            key=lambda kv: (-kv[1].article_count, kv[0]),
        )
        kept = 0
        for theme, counter in ranked:
            if kept >= top_n:
                break
            if counter.article_count < min_article_count:
                continue
            share = (
                counter.article_count / state.total_articles
                if state.total_articles > 0
                else 0.0
            )
            output.append(
                ThemeBucket(
                    country=country,
                    audience_type=audience,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                    theme=theme,
                    article_count=counter.article_count,
                    bucket_total=state.total_articles,
                    share=share,
                    avg_tone=counter.avg_tone,
                )
            )
            kept += 1

    # Stable final ordering
    output.sort(
        key=lambda b: (
            b.country,
            b.audience_type,
            b.period_start,
            -b.article_count,
            b.theme,
        )
    )
    return output


__all__ = [
    "PeriodType",
    "ThemeBucket",
    "aggregate_themes",
    "DEFAULT_TOP_N_PER_BUCKET",
    "DEFAULT_MIN_ARTICLE_COUNT",
]

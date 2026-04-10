"""30-day rolling baseline calculation — Algorithm 2 from SalientSignal-Algorithms.md.

For each (country, audience_type) tuple, we compute a baseline of "normal"
state media output by averaging the daily article counts over the last 30 days
(excluding today). This is the denominator that makes today's deviation
meaningful.

Public surface:

    Baseline                — dataclass holding mean / std / sample size
    calculate_baseline()    — pure-function variant that takes a list of daily counts
    fetch_baseline()        — DB-backed variant that reads from Supabase
"""
from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Iterable

logger = logging.getLogger(__name__)

# Days of history to use for the rolling average
BASELINE_WINDOW_DAYS = 30
# Minimum sample size before a baseline is considered usable
MIN_SAMPLE_DAYS = 7


@dataclass
class Baseline:
    """Result of a baseline calculation. None mean/std => not enough data."""

    mean: float
    std: float
    min_count: int
    max_count: int
    days_sampled: int

    @property
    def is_usable(self) -> bool:
        return self.days_sampled >= MIN_SAMPLE_DAYS

    @property
    def confidence(self) -> str:
        if self.days_sampled >= 21:
            return "HIGH"
        if self.days_sampled >= MIN_SAMPLE_DAYS:
            return "MEDIUM"
        return "LOW"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["confidence"] = self.confidence
        return d

    @classmethod
    def empty(cls) -> "Baseline":
        return cls(mean=0.0, std=0.0, min_count=0, max_count=0, days_sampled=0)


def calculate_baseline(daily_counts: Iterable[int]) -> Baseline:
    """Pure function: take a sequence of daily counts and return a Baseline.

    The pipeline normally calls `fetch_baseline` (DB-backed), but this version
    is convenient for unit tests and for in-memory recalculation.
    """
    counts = [int(c) for c in daily_counts]
    if not counts:
        return Baseline.empty()

    n = len(counts)
    mean = sum(counts) / n
    if n > 1:
        variance = sum((c - mean) ** 2 for c in counts) / n
        std = math.sqrt(variance)
    else:
        std = 0.0

    return Baseline(
        mean=round(mean, 2),
        std=round(std, 2),
        min_count=min(counts),
        max_count=max(counts),
        days_sampled=n,
    )


def fetch_baseline(
    db,
    country: str,
    audience_type: str,
    target_date: date,
    window_days: int = BASELINE_WINDOW_DAYS,
) -> Baseline:
    """Query the DB wrapper for daily article counts and compute the baseline.

    Args:
        db: a `db.SupabaseDb` instance (or compatible with `daily_article_counts`).
        country: ISO 3166-1 alpha-2 code.
        audience_type: DOMESTIC | INTERNATIONAL | DIASPORA.
        target_date: the day we're computing the baseline relative to (excluded
            from the window).
        window_days: how many days back to read.

    Returns:
        Baseline. If db is None or the query fails, returns Baseline.empty().
    """
    if db is None:
        logger.debug(
            "fetch_baseline(%s/%s) skipped — no db handle (likely dry-run)",
            country,
            audience_type,
        )
        return Baseline.empty()

    start = target_date - timedelta(days=window_days)
    end = target_date - timedelta(days=1)
    try:
        rows = db.daily_article_counts(
            country=country,
            audience_type=audience_type,
            start_date=start,
            end_date=end,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Baseline fetch failed for %s/%s: %s", country, audience_type, exc)
        return Baseline.empty()

    counts = [int(r["count"]) for r in rows] if rows else []
    return calculate_baseline(counts)


__all__ = [
    "Baseline",
    "calculate_baseline",
    "fetch_baseline",
    "BASELINE_WINDOW_DAYS",
    "MIN_SAMPLE_DAYS",
]

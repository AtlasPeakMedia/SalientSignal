"""Daily deviation + level mapping — Algorithm 2 from SalientSignal-Algorithms.md.

This module turns "today's article count" + "30-day baseline" into the
ratios, z-scores, and color levels that feed the globe.

Public surface:

    Deviation                 — dataclass with ratio, z_score, level, confidence
    calculate_deviation()     — pure function: take a Baseline + today's count
    deviation_to_level()      — color-bucket mapping shared with the frontend
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .baselines import Baseline

# Levels match the frontend `DeviationLevel` type in web/src/lib/dummy-data.ts.
# DO NOT change these strings without coordinating the frontend update.
LEVEL_DEEP_BLUE = "deepBlue"
LEVEL_STEEL_BLUE = "steelBlue"
LEVEL_COOL_GRAY = "coolGray"
LEVEL_NEUTRAL = "neutral"
LEVEL_AMBER = "amber"
LEVEL_ORANGE = "orange"
LEVEL_RED = "red"

ALL_LEVELS = (
    LEVEL_DEEP_BLUE,
    LEVEL_STEEL_BLUE,
    LEVEL_COOL_GRAY,
    LEVEL_NEUTRAL,
    LEVEL_AMBER,
    LEVEL_ORANGE,
    LEVEL_RED,
)


@dataclass
class Deviation:
    """Result of comparing today's count to a country's baseline."""

    today_count: int
    baseline_mean: float
    baseline_std: float
    ratio: float
    z_score: float
    level: str
    confidence: str  # LOW | MEDIUM | HIGH
    days_sampled: int

    def to_dict(self) -> dict:
        return asdict(self)


def deviation_to_level(ratio: float, z_score: float) -> str:
    """Map a ratio + z-score to a globe color level.

    Mirrors the JS `getLevel` function in `web/src/lib/dummy-data.ts` so the
    pipeline output and the frontend dummy data agree on visual encoding.

    Priority order (red team fix — DEV-C1 threshold ordering bug):
      1. Extreme z-score (>=2.5) wins regardless of ratio — real anomaly
      2. Warm-side spikes (ratio + z_score together) — moderate anomaly
      3. Cool-side silence checks (ratio + z_score together)
      4. Ratio-only fallbacks for LOW z-score cases

    The old ordering checked `ratio <= 1.5` BEFORE warm-side thresholds,
    which silently returned NEUTRAL for high-volume countries with small
    ratios but statistically significant z-scores (e.g. mean=100, std=10,
    today=130: ratio=1.3, z=3.0 → should be RED, was NEUTRAL).

    Both signals are still required for moderate spikes because:
      * ratio alone is misleading for noisy small countries
      * z-score alone is misleading for high-variance countries
    But extreme z-scores (>=2.5) are always considered a real anomaly.
    """
    # 1. Extreme z-score: genuine anomaly (wins over any ratio check)
    if z_score >= 2.5:
        return LEVEL_RED

    # 2. Warm-side spikes: both ratio AND z-score must agree
    if ratio <= 4.0 and z_score >= 2.0:
        return LEVEL_ORANGE
    if ratio <= 2.5 and z_score >= 1.5:
        return LEVEL_AMBER

    # 3. Cool-side silence: ratio AND z-score must agree
    if ratio < 0.3 and z_score < -2.0:
        return LEVEL_DEEP_BLUE
    if ratio < 0.5 and z_score < -1.5:
        return LEVEL_STEEL_BLUE
    if ratio < 0.75:
        return LEVEL_COOL_GRAY

    # 4. Ratio-only fallback for normal range (low z-score cases)
    # High ratio but low z-score = noisy country, falls through to neutral
    return LEVEL_NEUTRAL


# Sentinel z-score for "perfect consistency broken" — high enough to trigger RED
# but bounded so downstream math doesn't blow up.
_SENTINEL_Z_EXTREME = 10.0


def calculate_deviation(today_count: int, baseline: Baseline) -> Deviation:
    """Combine today's count with the baseline to produce a deviation result.

    Edge case handling (red team fixes DEV-C2, DEV-C3):

    1. Baseline unusable (< MIN_SAMPLE_DAYS): return NEUTRAL + LOW confidence.
    2. Baseline mean == 0 AND today == 0: country is consistently silent,
       return NEUTRAL (not noise, expected behavior).
    3. Baseline mean == 0 AND today > 0: ZERO-to-something spike.
       This is maximally anomalous — a country that has published nothing
       for 30 days suddenly publishing is a strong signal. Return RED with
       sentinel z-score.
    4. Baseline std == 0 AND today == mean: perfectly consistent, no change.
       Return NEUTRAL.
    5. Baseline std == 0 AND today != mean: ANY deviation from a perfectly
       consistent baseline is maximally anomalous. Return RED (spike) or
       DEEP_BLUE (silence) with sentinel z-score.
    """
    today = max(0, int(today_count))

    # Case 1: Baseline not usable yet
    if not baseline.is_usable:
        return Deviation(
            today_count=today,
            baseline_mean=baseline.mean,
            baseline_std=baseline.std,
            ratio=1.0,
            z_score=0.0,
            level=LEVEL_NEUTRAL,
            confidence=baseline.confidence,
            days_sampled=baseline.days_sampled,
        )

    # Case 2 & 3: mean == 0
    if baseline.mean == 0:
        if today == 0:
            # Consistently silent country — no signal, no anomaly
            return Deviation(
                today_count=today,
                baseline_mean=0.0,
                baseline_std=baseline.std,
                ratio=0.0,
                z_score=0.0,
                level=LEVEL_NEUTRAL,
                confidence=baseline.confidence,
                days_sampled=baseline.days_sampled,
            )
        # today > 0, mean == 0: zero-to-something spike, maximally anomalous
        return Deviation(
            today_count=today,
            baseline_mean=0.0,
            baseline_std=baseline.std,
            # ratio is mathematically undefined — use +inf semantically as float cap
            ratio=float(today),  # today / 1 floor for display
            z_score=_SENTINEL_Z_EXTREME,
            level=LEVEL_RED,
            confidence=baseline.confidence,
            days_sampled=baseline.days_sampled,
        )

    # Case 4 & 5: std == 0 (perfect consistency baseline)
    if baseline.std == 0:
        if today == baseline.mean:
            # Perfectly normal, no deviation
            return Deviation(
                today_count=today,
                baseline_mean=baseline.mean,
                baseline_std=0.0,
                ratio=1.0,
                z_score=0.0,
                level=LEVEL_NEUTRAL,
                confidence=baseline.confidence,
                days_sampled=baseline.days_sampled,
            )
        # ANY deviation from perfect consistency is anomalous
        ratio = today / baseline.mean
        if today > baseline.mean:
            return Deviation(
                today_count=today,
                baseline_mean=baseline.mean,
                baseline_std=0.0,
                ratio=round(ratio, 3),
                z_score=_SENTINEL_Z_EXTREME,
                level=LEVEL_RED,
                confidence=baseline.confidence,
                days_sampled=baseline.days_sampled,
            )
        else:
            return Deviation(
                today_count=today,
                baseline_mean=baseline.mean,
                baseline_std=0.0,
                ratio=round(ratio, 3),
                z_score=-_SENTINEL_Z_EXTREME,
                level=LEVEL_DEEP_BLUE,
                confidence=baseline.confidence,
                days_sampled=baseline.days_sampled,
            )

    # Normal case: baseline usable, mean > 0, std > 0
    ratio = today / baseline.mean
    z = (today - baseline.mean) / baseline.std

    level = deviation_to_level(ratio, z)
    return Deviation(
        today_count=today,
        baseline_mean=baseline.mean,
        baseline_std=baseline.std,
        ratio=round(ratio, 3),
        z_score=round(z, 3),
        level=level,
        confidence=baseline.confidence,
        days_sampled=baseline.days_sampled,
    )


__all__ = [
    "Deviation",
    "calculate_deviation",
    "deviation_to_level",
    "ALL_LEVELS",
    "LEVEL_DEEP_BLUE",
    "LEVEL_STEEL_BLUE",
    "LEVEL_COOL_GRAY",
    "LEVEL_NEUTRAL",
    "LEVEL_AMBER",
    "LEVEL_ORANGE",
    "LEVEL_RED",
]

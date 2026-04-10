"""Cross-country narrative coordination detection — Algorithm 6 (basic).

Phase 1/2 implements the simple version: for each GDELT theme that surged
in the last 24 hours, find which countries surged it together and return a
coordination event when 2+ countries align on the same theme above a
spike threshold (2x baseline).

Algorithm 6 in the spec also includes a "coordination_score" with bonuses for
known pairs (RU+CN, RU+IR, etc.); we implement that scoring here.

Public surface:

    detect_coordination(country_theme_spikes, time_window_hours=24)
    coordination_score(country_set, theme)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Spike threshold (today/baseline) above which a theme is considered "surging"
SURGE_THRESHOLD = 2.0
# Minimum number of countries needed to form a coordination event
MIN_COORDINATING_COUNTRIES = 2
# Minimum coordination score for the event to be persisted to the DB
MIN_COORDINATION_SCORE = 0.30


# Empirically observed coordination pairs (Algorithm 6)
KNOWN_PAIR_BONUSES: dict[frozenset[str], float] = {
    frozenset({"RU", "CN"}): 0.30,
    frozenset({"RU", "IR"}): 0.30,
    frozenset({"CN", "IR"}): 0.20,
    frozenset({"RU", "VE"}): 0.20,
    frozenset({"CU", "VE"}): 0.20,
    frozenset({"RU", "BY"}): 0.20,
    frozenset({"RU", "CN", "IR"}): 0.50,
    frozenset({"RU", "VE", "CU"}): 0.40,
}


@dataclass
class ThemeSpike:
    """One country's theme activity for the time window."""

    country: str
    theme: str
    article_count: int
    baseline: float
    ratio: float


@dataclass
class CoordinationEvent:
    theme: str
    countries: list[str]
    score: float
    time_window_hours: int = 24
    details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "theme": self.theme,
            "countries": self.countries,
            "coordination_score": round(self.score, 3),
            "time_window_hours": self.time_window_hours,
            "details": self.details,
        }


def coordination_score(country_set: set[str], n_countries: int) -> float:
    """Score how likely a multi-country theme spike represents real coordination.

    Components (matching Algorithm 6):
        * Pair bonus from KNOWN_PAIR_BONUSES (or zero)
        * Country bonus: more participating countries = stronger signal
    """
    frozen = frozenset(country_set)
    pair_bonus = KNOWN_PAIR_BONUSES.get(frozen, 0.0)
    if pair_bonus == 0.0:
        # Try every 2-country subset for partial credit
        as_list = sorted(country_set)
        for i in range(len(as_list)):
            for j in range(i + 1, len(as_list)):
                sub = frozenset({as_list[i], as_list[j]})
                pair_bonus = max(pair_bonus, KNOWN_PAIR_BONUSES.get(sub, 0.0))
    country_bonus = min((n_countries - 1) * 0.15, 0.45)
    return min(pair_bonus + country_bonus + 0.10, 1.0)  # +0.10 floor for any 2-country spike


def detect_coordination(
    spikes: list[ThemeSpike],
    *,
    time_window_hours: int = 24,
    surge_threshold: float = SURGE_THRESHOLD,
    min_countries: int = MIN_COORDINATING_COUNTRIES,
    min_score: float = MIN_COORDINATION_SCORE,
) -> list[CoordinationEvent]:
    """Group spikes by theme and emit coordination events.

    Args:
        spikes: list of (country, theme, count, baseline, ratio).
        surge_threshold: ratio above which a theme is considered "surging".
        min_countries: minimum participating countries (default 2).
        min_score: minimum coordination_score to emit.
    """
    by_theme: dict[str, list[ThemeSpike]] = defaultdict(list)
    for spike in spikes:
        if spike.ratio >= surge_threshold:
            by_theme[spike.theme].append(spike)

    events: list[CoordinationEvent] = []
    for theme, theme_spikes in by_theme.items():
        countries = sorted({s.country for s in theme_spikes})
        if len(countries) < min_countries:
            continue
        score = coordination_score(set(countries), len(countries))
        if score < min_score:
            continue
        events.append(
            CoordinationEvent(
                theme=theme,
                countries=countries,
                score=score,
                time_window_hours=time_window_hours,
                details=[
                    {
                        "country": s.country,
                        "article_count": s.article_count,
                        "baseline": s.baseline,
                        "ratio": round(s.ratio, 2),
                    }
                    for s in theme_spikes
                ],
            )
        )

    events.sort(key=lambda e: e.score, reverse=True)
    return events


__all__ = [
    "ThemeSpike",
    "CoordinationEvent",
    "coordination_score",
    "detect_coordination",
    "SURGE_THRESHOLD",
    "MIN_COORDINATING_COUNTRIES",
    "MIN_COORDINATION_SCORE",
    "KNOWN_PAIR_BONUSES",
]

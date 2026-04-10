"""Tests for deviation.py — Algorithm 2 level mapping and edge cases.

Covers the red team CRITICAL findings:
  - DEV-C1: threshold ordering bug (high z-score + low ratio should not be NEUTRAL)
  - DEV-C2: std=0 edge case (perfect consistency broken)
  - DEV-C3: mean=0 edge case (zero-to-something spike)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.baselines import Baseline
from src.deviation import (
    LEVEL_AMBER,
    LEVEL_COOL_GRAY,
    LEVEL_DEEP_BLUE,
    LEVEL_NEUTRAL,
    LEVEL_ORANGE,
    LEVEL_RED,
    LEVEL_STEEL_BLUE,
    calculate_deviation,
    deviation_to_level,
)


def _baseline(mean: float, std: float, days: int = 30) -> Baseline:
    """Helper: build a Baseline for tests."""
    return Baseline(mean=mean, std=std, days_sampled=days, min_count=0, max_count=int(mean * 4))


# ---------------------------------------------------------------------------
# DEV-C1: Threshold ordering — high z-score should win over low ratio
# ---------------------------------------------------------------------------
class TestThresholdOrdering:
    def test_high_z_score_low_ratio_returns_red(self):
        """mean=100, std=10, today=130 → ratio=1.3, z=3.0 → RED (was NEUTRAL)."""
        # z >= 2.5 should trigger RED regardless of ratio
        assert deviation_to_level(ratio=1.3, z_score=3.0) == LEVEL_RED

    def test_high_z_score_overrides_neutral_ratio(self):
        """A 3-sigma spike wins even if ratio is only 1.2."""
        assert deviation_to_level(ratio=1.2, z_score=4.0) == LEVEL_RED

    def test_extreme_ratio_low_z_stays_neutral(self):
        """Noisy country: ratio=3.0 but z=1.0 should stay NEUTRAL."""
        assert deviation_to_level(ratio=3.0, z_score=1.0) == LEVEL_NEUTRAL

    def test_moderate_amber_threshold(self):
        """ratio<=2.5 AND z>=1.5 → AMBER."""
        assert deviation_to_level(ratio=2.0, z_score=1.8) == LEVEL_AMBER

    def test_moderate_orange_threshold(self):
        """ratio<=4.0 AND z>=2.0 → ORANGE."""
        assert deviation_to_level(ratio=3.5, z_score=2.2) == LEVEL_ORANGE

    def test_deep_blue_silence(self):
        """ratio<0.3 AND z<-2.0 → DEEP_BLUE."""
        assert deviation_to_level(ratio=0.2, z_score=-3.0) == LEVEL_DEEP_BLUE

    def test_steel_blue_unusually_quiet(self):
        """ratio<0.5 AND z<-1.5 → STEEL_BLUE."""
        assert deviation_to_level(ratio=0.4, z_score=-1.8) == LEVEL_STEEL_BLUE

    def test_cool_gray_slightly_quiet(self):
        """ratio<0.75 (no strong z-score) → COOL_GRAY."""
        assert deviation_to_level(ratio=0.6, z_score=-0.5) == LEVEL_COOL_GRAY

    def test_normal_range(self):
        """ratio in [0.75, 1.5] → NEUTRAL."""
        assert deviation_to_level(ratio=1.0, z_score=0.0) == LEVEL_NEUTRAL
        assert deviation_to_level(ratio=1.3, z_score=0.5) == LEVEL_NEUTRAL

    def test_red_wins_over_amber_when_z_is_extreme(self):
        """z=3.0 with ratio=2.0 — z wins → RED (not AMBER)."""
        assert deviation_to_level(ratio=2.0, z_score=3.0) == LEVEL_RED


# ---------------------------------------------------------------------------
# DEV-C2: std=0 edge case
# ---------------------------------------------------------------------------
class TestStdZeroEdgeCase:
    def test_perfectly_consistent_baseline_spike_returns_red(self):
        """Country publishes exactly 10/day for 30 days, today=50 → RED."""
        baseline = _baseline(mean=10.0, std=0.0, days=30)
        result = calculate_deviation(today_count=50, baseline=baseline)
        assert result.level == LEVEL_RED
        assert result.z_score == 10.0  # sentinel value

    def test_perfectly_consistent_baseline_drop_returns_deep_blue(self):
        """Country publishes exactly 10/day for 30 days, today=0 → DEEP_BLUE."""
        baseline = _baseline(mean=10.0, std=0.0, days=30)
        result = calculate_deviation(today_count=0, baseline=baseline)
        assert result.level == LEVEL_DEEP_BLUE
        assert result.z_score == -10.0

    def test_perfectly_consistent_baseline_matching_today_returns_neutral(self):
        """Country publishes exactly 10/day for 30 days, today=10 → NEUTRAL."""
        baseline = _baseline(mean=10.0, std=0.0, days=30)
        result = calculate_deviation(today_count=10, baseline=baseline)
        assert result.level == LEVEL_NEUTRAL
        assert result.z_score == 0.0


# ---------------------------------------------------------------------------
# DEV-C3: mean=0 edge case
# ---------------------------------------------------------------------------
class TestMeanZeroEdgeCase:
    def test_zero_baseline_zero_today_returns_neutral(self):
        """Consistently silent country (7 days zeros, today zero) → NEUTRAL."""
        baseline = _baseline(mean=0.0, std=0.0, days=30)
        result = calculate_deviation(today_count=0, baseline=baseline)
        assert result.level == LEVEL_NEUTRAL

    def test_zero_baseline_spike_returns_red(self):
        """Consistently silent country suddenly publishes → RED."""
        baseline = _baseline(mean=0.0, std=0.0, days=30)
        result = calculate_deviation(today_count=5, baseline=baseline)
        assert result.level == LEVEL_RED
        assert result.z_score == 10.0


# ---------------------------------------------------------------------------
# Baseline usability edge cases (unrelated to C1/C2/C3 but important)
# ---------------------------------------------------------------------------
class TestUnusableBaseline:
    def test_too_few_days_returns_neutral(self):
        """Baseline with <7 days → NEUTRAL + LOW confidence."""
        baseline = _baseline(mean=5.0, std=2.0, days=3)
        result = calculate_deviation(today_count=50, baseline=baseline)
        # 3 days < MIN_SAMPLE_DAYS=7 → not usable
        assert result.level == LEVEL_NEUTRAL


# ---------------------------------------------------------------------------
# Standard cases that should still work (regression tests)
# ---------------------------------------------------------------------------
class TestStandardCases:
    def test_normal_day_returns_neutral(self):
        """mean=25, std=8, today=28 → within normal range."""
        baseline = _baseline(mean=25.0, std=8.0, days=30)
        result = calculate_deviation(today_count=28, baseline=baseline)
        assert result.level == LEVEL_NEUTRAL

    def test_genuine_spike_returns_red(self):
        """mean=25, std=8, today=85 → ratio=3.4, z=7.5 → RED."""
        baseline = _baseline(mean=25.0, std=8.0, days=30)
        result = calculate_deviation(today_count=85, baseline=baseline)
        assert result.level == LEVEL_RED

    def test_silence_returns_deep_blue(self):
        """mean=50, std=10, today=5 → ratio=0.1, z=-4.5 → DEEP_BLUE."""
        baseline = _baseline(mean=50.0, std=10.0, days=30)
        result = calculate_deviation(today_count=5, baseline=baseline)
        assert result.level == LEVEL_DEEP_BLUE

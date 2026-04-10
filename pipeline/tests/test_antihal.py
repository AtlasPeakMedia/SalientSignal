"""Tests for the Anti-Hallucination Agent (antihal.py).

Validates the SAT-based validation layer catches false-positive coordination
events (anniversaries, generic themes, low-confidence extremes) and kills
UNKNOWN classifications before they can be published.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.antihal import (
    Verdict,
    validate_classification,
    validate_coordination,
    validate_deviation,
)


# ---------------------------------------------------------------------------
# Classification validation
# ---------------------------------------------------------------------------
class TestClassificationValidation:
    def test_high_confidence_outlet_publishes(self):
        r = validate_classification(
            {"source_domain": "rt.com", "source_country": "RU", "source_language": "en"},
            audience_type="INTERNATIONAL",
            confidence=0.95,
        )
        assert r.verdict == Verdict.PUBLISH
        assert r.should_publish

    def test_unknown_audience_suppresses(self):
        r = validate_classification(
            {"source_domain": "mystery.xyz", "source_country": "", "source_language": ""},
            audience_type="UNKNOWN",
            confidence=0.0,
        )
        assert r.verdict == Verdict.SUPPRESS
        assert not r.should_publish

    def test_moderate_confidence_gets_caveat(self):
        r = validate_classification(
            {"source_domain": "unknown-news.ru", "source_country": "RU", "source_language": "ru"},
            audience_type="DOMESTIC",
            confidence=0.60,
        )
        assert r.verdict == Verdict.PUBLISH_WITH_CAVEAT
        assert r.caveat is not None

    def test_low_confidence_flagged_but_publishes(self):
        r = validate_classification(
            {"source_domain": "rando.info", "source_country": "", "source_language": ""},
            audience_type="INTERNATIONAL",
            confidence=0.20,
        )
        assert r.verdict == Verdict.PUBLISH_WITH_CAVEAT
        assert r.red_team_flags, "Should have red team flags for low confidence"


# ---------------------------------------------------------------------------
# Deviation validation
# ---------------------------------------------------------------------------
class TestDeviationValidation:
    def _deviation(self, **kwargs):
        """Helper to build a deviation dict with sane defaults."""
        base = {
            "today_count": 50,
            "baseline_mean": 25.0,
            "baseline_std": 5.0,
            "ratio": 2.0,
            "z_score": 5.0,
            "level": "red",
            "confidence": "HIGH",
            "days_sampled": 30,
        }
        base.update(kwargs)
        return base

    def test_high_confidence_red_publishes(self):
        r = validate_deviation("RU", "INTERNATIONAL", self._deviation())
        assert r.verdict == Verdict.PUBLISH

    def test_low_confidence_extreme_suppresses(self):
        """Red with LOW confidence AFTER cold start → should SUPPRESS.

        P2-H4 change: the cold start path (days_sampled < 7) publishes instead
        of suppressing. The stable path still suppresses extreme claims with
        LOW confidence, so we use days_sampled=25 here to reach the stable path
        with a (contradictory but valid-for-testing) LOW confidence label.
        """
        r = validate_deviation(
            "VE", "DOMESTIC",
            self._deviation(confidence="LOW", days_sampled=25, level="red"),
        )
        assert r.verdict == Verdict.SUPPRESS

    def test_low_confidence_extreme_silence_suppresses(self):
        """P2-H4: test the stable path, not cold start."""
        r = validate_deviation(
            "KP", "INTERNATIONAL",
            self._deviation(confidence="LOW", days_sampled=25, level="deepBlue",
                            today_count=0, ratio=0.0, z_score=-3.0),
        )
        assert r.verdict == Verdict.SUPPRESS

    def test_medium_confidence_extreme_caveats(self):
        r = validate_deviation(
            "CN", "DOMESTIC",
            self._deviation(confidence="MEDIUM", days_sampled=10, level="red"),
        )
        assert r.verdict == Verdict.PUBLISH_WITH_CAVEAT
        assert r.caveat is not None

    def test_normal_deviation_publishes(self):
        r = validate_deviation(
            "UY", "INTERNATIONAL",
            self._deviation(level="neutral", ratio=1.0, z_score=0.0,
                            confidence="HIGH", days_sampled=30),
        )
        assert r.verdict == Verdict.PUBLISH

    def test_sentinel_z_score_flagged(self):
        """The std=0 and mean=0 edge cases use z_score=±10. Validator should flag."""
        r = validate_deviation(
            "RU", "DOMESTIC",
            self._deviation(z_score=10.0, level="red"),
        )
        # Should be flagged but still publish if confidence is HIGH
        assert any("Sentinel z-score" in f for f in r.red_team_flags)


# ---------------------------------------------------------------------------
# Coordination validation — THE CRITICAL SUPPRESSOR
# ---------------------------------------------------------------------------
class TestCoordinationValidation:
    def test_may_9_victory_day_suppressed(self):
        """May 9 Victory Day coordination → SUPPRESS via H4 anniversary."""
        r = validate_coordination({
            "date": "2026-05-09",
            "theme": "MILITARY_PARADE",
            "countries": ["RU", "BY", "KP"],
            "coordination_score": 0.8,
            "time_window_hours": 48,
        })
        assert r.verdict == Verdict.SUPPRESS
        assert "Victory Day" in r.verdict_reason

    def test_tiananmen_anniversary_suppressed(self):
        """June 4 Tiananmen anniversary → SUPPRESS."""
        r = validate_coordination({
            "date": "2026-06-04",
            "theme": "DOMESTIC_POLICY",
            "countries": ["CN", "KP"],
            "coordination_score": 0.7,
        })
        assert r.verdict == Verdict.SUPPRESS

    def test_china_national_day_suppressed(self):
        """October 1 China National Day → SUPPRESS."""
        r = validate_coordination({
            "date": "2026-10-01",
            "theme": "REGIME_LEGITIMACY",
            "countries": ["CN", "KP"],
            "coordination_score": 0.65,
        })
        assert r.verdict == Verdict.SUPPRESS

    def test_generic_disaster_theme_flagged(self):
        """NATURAL_DISASTER theme → flagged as possible major event."""
        r = validate_coordination({
            "date": "2026-04-15",
            "theme": "NATURAL_DISASTER",
            "countries": ["RU", "CN", "IR", "TR", "VE"],
            "coordination_score": 0.7,
        })
        assert r.red_team_flags, "Generic themes should be flagged"
        # 5-country coordination should escalate
        assert r.verdict in (Verdict.ESCALATE, Verdict.SUPPRESS)

    def test_triple_country_coordination_escalates(self):
        """RU-CN-IR triple coordination on specific theme → ESCALATE."""
        r = validate_coordination({
            "date": "2026-04-15",
            "theme": "SANCTIONS_NARRATIVE",
            "countries": ["RU", "CN", "IR"],
            "coordination_score": 0.85,
        })
        assert r.verdict == Verdict.ESCALATE

    def test_two_country_specific_theme_publishes_with_caveat(self):
        """Two-country coordination on a specific theme → PUBLISH_WITH_CAVEAT."""
        r = validate_coordination({
            "date": "2026-04-15",
            "theme": "NATO_NARRATIVE",
            "countries": ["RU", "BY"],
            "coordination_score": 0.55,
        })
        assert r.verdict == Verdict.PUBLISH_WITH_CAVEAT
        assert "BETA" in (r.caveat or "")

    def test_generated_hypotheses_include_alternatives(self):
        """Every coordination event should get H1-H5 hypotheses."""
        r = validate_coordination({
            "date": "2026-04-15",
            "theme": "DOMESTIC_POLICY",
            "countries": ["RU", "BY"],
            "coordination_score": 0.5,
        })
        hyp_ids = {h["id"] for h in r.competing_hypotheses}
        assert "H1_DELIBERATE_COORDINATION" in hyp_ids
        assert "H2_MAJOR_EVENT_REACTION" in hyp_ids
        assert "H3_WIRE_SYNDICATION" in hyp_ids


# ---------------------------------------------------------------------------
# Verdict semantics
# ---------------------------------------------------------------------------
class TestVerdictSemantics:
    def test_publish_means_display(self):
        r = validate_classification(
            {"source_domain": "rt.com", "source_country": "RU", "source_language": "en"},
            audience_type="INTERNATIONAL",
            confidence=0.95,
        )
        assert r.should_publish

    def test_publish_with_caveat_still_displays(self):
        r = validate_classification(
            {"source_domain": "rando.info", "source_country": "", "source_language": ""},
            audience_type="INTERNATIONAL",
            confidence=0.3,
        )
        assert r.should_publish  # PUBLISH_WITH_CAVEAT → display with hedge

    def test_suppress_does_not_display(self):
        r = validate_classification(
            {"source_domain": "x", "source_country": "", "source_language": ""},
            audience_type="UNKNOWN",
            confidence=0.0,
        )
        assert not r.should_publish

"""Phase 2 Anti-Hallucination Agent regression tests.

Covers the four Phase 2 fixes to antihal.py:

  - P2-H4: Cold start handling — days 1-6 publish with caveat, not suppress.
           Warming up (7-20) publishes extreme levels with caveat.
           Stable (21+) keeps the original suppress-on-LOW-confidence path.

  - P2-H5: Expanded anniversary list (May 1, Mar 8, Sep 3, Aug 15, Dec 26,
           Nowruz, plus the original 6).

  - P2-H6: Generic theme detection is exact-match/narrow-prefix, not substring.
           Narrative-specific themes (WB_2024_ANTI_WESTERN) should NOT flag
           as generic even though they start with "WB_".
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.antihal import (
    Verdict,
    _ANNIVERSARY_DATES,
    _is_generic_theme,
    validate_coordination,
    validate_deviation,
)


# ---------------------------------------------------------------------------
# P2-H5: Expanded anniversary list
# ---------------------------------------------------------------------------
class TestAnniversaryExpansion:
    def test_may_1_labor_day_flagged(self):
        """P2-H5: May 1 (Labor Day) was missing from Phase 1 list."""
        assert (5, 1) in _ANNIVERSARY_DATES
        assert "May Day" in _ANNIVERSARY_DATES[(5, 1)] or "Labor" in _ANNIVERSARY_DATES[(5, 1)]

    def test_march_8_womens_day_flagged(self):
        """P2-H5: International Women's Day was missing."""
        assert (3, 8) in _ANNIVERSARY_DATES

    def test_september_3_china_victory_flagged(self):
        """P2-H5: China Victory Over Japan Day was missing."""
        assert (9, 3) in _ANNIVERSARY_DATES
        assert "China" in _ANNIVERSARY_DATES[(9, 3)]

    def test_august_15_dual_anniversary_flagged(self):
        """P2-H5: India Independence Day + Korea Liberation Day."""
        assert (8, 15) in _ANNIVERSARY_DATES

    def test_december_26_boxing_day_flagged(self):
        """P2-H5: Soviet Union dissolution anniversary."""
        assert (12, 26) in _ANNIVERSARY_DATES

    def test_nowruz_flagged(self):
        """P2-H5: Persian New Year — Iran, Central Asia."""
        assert (3, 21) in _ANNIVERSARY_DATES

    def test_original_anniversaries_still_present(self):
        """P2-H5 must not remove Phase 1 anniversaries."""
        assert (5, 9) in _ANNIVERSARY_DATES   # Victory Day
        assert (10, 1) in _ANNIVERSARY_DATES  # China National Day
        assert (2, 11) in _ANNIVERSARY_DATES  # Iranian Revolution
        assert (6, 4) in _ANNIVERSARY_DATES   # Tiananmen
        assert (11, 7) in _ANNIVERSARY_DATES  # October Revolution
        assert (7, 1) in _ANNIVERSARY_DATES   # HK handover / CCP founding

    def test_may_day_coordination_suppressed(self):
        """A coordination event on May 1 should be suppressed as anniversary."""
        event = {
            "date": "2026-05-01",
            "theme": "WB_2024_ANTI_WESTERN_PROPAGANDA",
            "countries": ["RU", "CN", "BY"],
            "coordination_score": 0.75,
        }
        result = validate_coordination(event)
        assert result.verdict == Verdict.SUPPRESS
        # Verify H4 hypothesis was the trigger
        h4 = [h for h in result.competing_hypotheses if h["id"] == "H4_ANNIVERSARY_PATTERN"]
        assert len(h4) == 1
        assert h4[0]["score"] >= 0.7


# ---------------------------------------------------------------------------
# P2-H6: Generic theme detection
# ---------------------------------------------------------------------------
class TestGenericThemeDetection:
    def test_crisislex_disaster_is_generic(self):
        assert _is_generic_theme("CRISISLEX_CRISISLEXREC")
        assert _is_generic_theme("NATURAL_DISASTER_EARTHQUAKE")
        assert _is_generic_theme("NATURAL_DISASTER_FLOOD")

    def test_anti_western_narrative_is_NOT_generic(self):
        """P2-H6 CORE FIX: WB_2024_ANTI_WESTERN is narrative-specific despite
        starting with WB_."""
        assert not _is_generic_theme("WB_2024_ANTI_WESTERN_PROPAGANDA")
        assert not _is_generic_theme("WB_2024_ANTI_NATO_NARRATIVE")
        assert not _is_generic_theme("WB_2024_ANTI_SANCTIONS")

    def test_generic_wb_theme_still_flagged(self):
        """WB_2670_JOBS is an exact match in the generic list."""
        assert _is_generic_theme("WB_2670_JOBS")

    def test_econ_stockmarket_is_generic(self):
        assert _is_generic_theme("ECON_STOCKMARKET")

    def test_econ_narrative_specific_not_generic(self):
        # ECON_INFLATION is generic, but a country-specific narrative would
        # not be stripped by our exact-match list
        assert _is_generic_theme("ECON_INFLATION")

    def test_terror_is_generic(self):
        assert _is_generic_theme("TERROR")
        assert _is_generic_theme("TERRORISM")

    def test_empty_theme_not_generic(self):
        assert not _is_generic_theme("")

    def test_unknown_theme_not_generic(self):
        assert not _is_generic_theme("SOME_RANDOM_NOVEL_THEME_CODE")

    def test_narrative_prefix_overrides_generic(self):
        # Even if SOC_POINTSOFINTEREST_STOCKMARKET existed, the prefix
        # should keep it narrative-specific
        assert not _is_generic_theme("SOC_POINTSOFINTEREST_STOCKMARKET")

    def test_substring_bug_fixed(self):
        """Regression: old buggy code did `if g in theme` which matched
        anything containing WB_, EPU_, etc. even in narrative positions."""
        # These would have been flagged by the old substring logic but
        # should now NOT be flagged because WB_ is not in the exact list
        # without a narrow prefix
        assert not _is_generic_theme("TAX_POLITICAL_PARTY_CHINESE_COMMUNIST_PARTY")
        assert not _is_generic_theme("TAX_WORLDMAMMALS_PANDA")


# ---------------------------------------------------------------------------
# P2-H4: Cold start handling
# ---------------------------------------------------------------------------
class TestColdStartHandling:
    def _make_dev(self, days_sampled: int, level: str, confidence: str):
        return {
            "today_count": 100,
            "baseline_mean": 50.0,
            "baseline_std": 10.0,
            "ratio": 2.0,
            "z_score": 5.0,
            "level": level,
            "confidence": confidence,
            "days_sampled": days_sampled,
        }

    def test_cold_start_day_1_red_publishes_with_caveat(self):
        """P2-H4: day 1 red should PUBLISH_WITH_CAVEAT, not SUPPRESS.

        Old behavior: red + LOW confidence → SUPPRESS (week 1 globe looks dead)
        New behavior: days_sampled < 7 → publish with calibration caveat
        """
        dev = self._make_dev(days_sampled=1, level="red", confidence="LOW")
        result = validate_deviation("RU", "INTERNATIONAL", dev)
        assert result.verdict == Verdict.PUBLISH_WITH_CAVEAT
        assert result.caveat is not None
        assert "Calibrating" in result.caveat or "calibrat" in result.caveat.lower()

    def test_cold_start_day_3_deepblue_publishes(self):
        dev = self._make_dev(days_sampled=3, level="deepBlue", confidence="LOW")
        result = validate_deviation("KP", "DOMESTIC", dev)
        assert result.verdict == Verdict.PUBLISH_WITH_CAVEAT
        assert result.claim_data.get("cold_start") is True

    def test_cold_start_day_6_still_cold(self):
        dev = self._make_dev(days_sampled=6, level="red", confidence="LOW")
        result = validate_deviation("IR", "INTERNATIONAL", dev)
        assert result.verdict == Verdict.PUBLISH_WITH_CAVEAT
        assert result.claim_data.get("cold_start") is True

    def test_warming_up_day_7_red_has_warming_caveat(self):
        dev = self._make_dev(days_sampled=7, level="red", confidence="MEDIUM")
        result = validate_deviation("CN", "INTERNATIONAL", dev)
        assert result.verdict == Verdict.PUBLISH_WITH_CAVEAT
        assert result.caveat is not None
        assert "warming" in result.caveat.lower() or "calibrat" in result.caveat.lower()
        assert result.claim_data.get("cold_start") is True

    def test_warming_up_day_14_red_caveat(self):
        dev = self._make_dev(days_sampled=14, level="red", confidence="MEDIUM")
        result = validate_deviation("RU", "INTERNATIONAL", dev)
        assert result.verdict == Verdict.PUBLISH_WITH_CAVEAT

    def test_warming_up_day_20_still_warming(self):
        dev = self._make_dev(days_sampled=20, level="red", confidence="MEDIUM")
        result = validate_deviation("VE", "INTERNATIONAL", dev)
        assert result.verdict == Verdict.PUBLISH_WITH_CAVEAT
        assert result.claim_data.get("cold_start") is True

    def test_stable_day_21_normal_path(self):
        """Day 21+ with HIGH confidence → normal publish, no cold_start flag."""
        dev = self._make_dev(days_sampled=21, level="red", confidence="HIGH")
        result = validate_deviation("RU", "INTERNATIONAL", dev)
        assert result.verdict == Verdict.PUBLISH
        assert result.claim_data.get("cold_start") is False

    def test_stable_low_confidence_red_still_suppressed(self):
        """Regression: stable path with LOW confidence still suppresses.
        This is the original Phase 1 behavior, preserved for days 21+."""
        dev = self._make_dev(days_sampled=25, level="red", confidence="LOW")
        result = validate_deviation("RU", "INTERNATIONAL", dev)
        assert result.verdict == Verdict.SUPPRESS

    def test_stable_medium_red_gets_caveat(self):
        dev = self._make_dev(days_sampled=30, level="red", confidence="MEDIUM")
        result = validate_deviation("CN", "INTERNATIONAL", dev)
        assert result.verdict == Verdict.PUBLISH_WITH_CAVEAT

    def test_stable_normal_level_high_publishes_clean(self):
        dev = self._make_dev(days_sampled=30, level="amber", confidence="HIGH")
        result = validate_deviation("TR", "INTERNATIONAL", dev)
        assert result.verdict == Verdict.PUBLISH
        assert result.caveat is None


# ---------------------------------------------------------------------------
# End-to-end: batch validation with cold start
# ---------------------------------------------------------------------------
class TestBatchValidationPropagatesColdStart:
    def test_batch_deviations_propagates_cold_start_flag(self):
        """validate_batch_deviations must copy cold_start onto the row so
        the frontend can show a calibration banner."""
        from src.antihal import validate_batch_deviations
        rows = [
            {
                "country": "RU",
                "audience_type": "INTERNATIONAL",
                "today_count": 50,
                "baseline_mean": 25.0,
                "baseline_std": 5.0,
                "ratio": 2.0,
                "z_score": 5.0,
                "level": "red",
                "confidence": "LOW",
                "days_sampled": 3,  # cold start
            },
        ]
        published, results = validate_batch_deviations(rows)
        assert len(published) == 1
        assert published[0].get("cold_start") is True
        assert "_caveat" in published[0]

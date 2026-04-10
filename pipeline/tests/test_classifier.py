"""Tests for classifier.py — Algorithm 1 audience classification.

Covers red team CRITICAL findings:
  - CLA-C1: Unknown data should NOT default to INTERNATIONAL 100%
  - CLA-C3: Weight normalization must be against theoretical max, not activated sum
  - CLA-C4: New/unknown outlets require multi-signal agreement for high confidence
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.classifier import Article, classify_audience


def _article(domain: str = "", language: str = "", country: str = "") -> Article:
    return Article(
        url="", domain=domain, source_country=country, language=language, title=""
    )


# ---------------------------------------------------------------------------
# CLA-C1: Unknown data should NOT return 100% confidence
# ---------------------------------------------------------------------------
class TestUnknownDataConfidence:
    def test_all_unknown_returns_unknown(self):
        """Domain not in DB, no language, no country → UNKNOWN."""
        r = classify_audience(_article(domain="mystery.xyz", language="", country=""))
        # Either UNKNOWN or a very low-confidence classification
        assert r[1] < 0.60, f"Confidence should be low, got {r}"

    def test_generic_tld_only_is_low_confidence(self):
        """Only TLD signal fires (generic .info domain) → low confidence."""
        r = classify_audience(_article(domain="newsite.info", language="", country=""))
        assert r[1] < 0.60, f"Single-signal confidence should be capped, got {r}"

    def test_unknown_outlet_generic_tld_capped(self):
        """No outlet lookup, no strong language/platform signal → confidence capped."""
        r = classify_audience(_article(domain="mysterious.news", language="??", country="ZZ"))
        assert r[1] < 0.60, f"Fallback confidence should be low, got {r}"


# ---------------------------------------------------------------------------
# CLA-C3: Weight normalization against theoretical max
# ---------------------------------------------------------------------------
class TestWeightNormalization:
    def test_single_signal_does_not_produce_full_confidence(self):
        """A single weak signal should not produce 1.0 confidence."""
        r = classify_audience(_article(domain="rando.info", language="", country=""))
        assert r[1] < 1.0, "Single TLD signal must not return 1.0 confidence"

    def test_multiple_agreeing_signals_produce_moderate_confidence(self):
        """New Russian outlet in Russian language — 2 signals agree on DOMESTIC."""
        # newrussianoutlet.ru is not in DB, but:
        #   - language 'ru' matches Russia's official language → DOMESTIC
        #   - TLD .ru → DOMESTIC
        # Two signals agree → higher confidence than single-signal
        r = classify_audience(_article(domain="newrussianoutlet.ru", language="ru", country="RU"))
        assert r[0] == "DOMESTIC"
        assert r[1] >= 0.30, f"Two-signal agreement should be >0.30, got {r}"


# ---------------------------------------------------------------------------
# CLA-C4: Unknown outlets require multi-signal evidence
# ---------------------------------------------------------------------------
class TestUnknownOutletEvasion:
    def test_new_state_outlet_with_language_only(self):
        """Unknown Russian-language outlet from RU — language is only signal."""
        r = classify_audience(_article(domain="freshrunews.press", language="ru", country="RU"))
        # Should classify as DOMESTIC but with lower-than-outlet-lookup confidence
        assert r[0] == "DOMESTIC"
        assert r[1] < 0.85, f"Language-only should be below outlet-lookup, got {r}"


# ---------------------------------------------------------------------------
# Diaspora detection (CLA-C2 fix — more languages now supported)
# ---------------------------------------------------------------------------
class TestDiasporaDetection:
    def test_russia_german_content_is_diaspora(self):
        """Russia-origin content in German → DIASPORA targeting."""
        r = classify_audience(_article(domain="unknown.de", language="de", country="RU"))
        assert r[0] == "DIASPORA"

    def test_china_indonesian_content_is_diaspora(self):
        """China-origin content in Indonesian → DIASPORA targeting Chinese-Indonesians."""
        r = classify_audience(_article(domain="unknown.id", language="id", country="CN"))
        assert r[0] == "DIASPORA"

    def test_turkey_german_content_is_diaspora(self):
        """Turkey-origin content in German → Turkish diaspora in Germany."""
        r = classify_audience(_article(domain="unknown.de", language="de", country="TR"))
        assert r[0] == "DIASPORA"

    def test_russia_russian_content_is_domestic(self):
        """Russia-origin content in Russian → DOMESTIC (not diaspora)."""
        r = classify_audience(_article(domain="unknown.ru", language="ru", country="RU"))
        assert r[0] == "DOMESTIC"


# ---------------------------------------------------------------------------
# Outlet database lookups still work (regression tests)
# ---------------------------------------------------------------------------
class TestOutletDatabaseLookups:
    def test_rt_com_is_international(self):
        r = classify_audience(_article(domain="rt.com", language="en", country="RU"))
        assert r[0] == "INTERNATIONAL"
        assert r[1] >= 0.85, f"rt.com should have high confidence, got {r}"

    def test_tass_ru_is_domestic(self):
        r = classify_audience(_article(domain="tass.ru", language="ru", country="RU"))
        assert r[0] == "DOMESTIC"
        assert r[1] >= 0.85

    def test_cgtn_com_is_international(self):
        r = classify_audience(_article(domain="cgtn.com", language="en", country="CN"))
        assert r[0] == "INTERNATIONAL"
        assert r[1] >= 0.85

    def test_cctv_com_is_domestic(self):
        r = classify_audience(_article(domain="cctv.com", language="zh", country="CN"))
        assert r[0] == "DOMESTIC"
        assert r[1] >= 0.85

    def test_press_tv_is_international(self):
        r = classify_audience(_article(domain="presstv.ir", language="en", country="IR"))
        assert r[0] == "INTERNATIONAL"
        assert r[1] >= 0.85


# ---------------------------------------------------------------------------
# FVEY exclusion (no classifications for US/UK/CA/AU/NZ)
# ---------------------------------------------------------------------------
class TestFVEYExclusion:
    def test_cnn_not_in_outlets_db(self):
        """CNN is US media — should NOT have an outlet lookup."""
        from src.outlets import get_outlet
        assert get_outlet("cnn.com") is None

    def test_bbc_not_in_outlets_db(self):
        from src.outlets import get_outlet
        assert get_outlet("bbc.co.uk") is None

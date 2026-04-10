"""Phase 2 domain normalization tests (P2-C3).

Validates that `_normalize_domain` correctly extracts the canonical hostname
from every real-world URL format GDELT can return. Before this fix, the
old code only matched ~40-60% of real GDELT output because it expected
bare hostnames and choked on URLs, www prefixes, ports, paths, etc.

See SalientSignal-Phase1-Review.md and proud-jumping-key.md Phase 2 red team
findings (P2-C3) for the full failure enumeration.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.outlets import _normalize_domain, get_outlet


class TestNormalizeDomain:
    def test_bare_hostname(self):
        assert _normalize_domain("rt.com") == "rt.com"

    def test_empty_string(self):
        assert _normalize_domain("") == ""

    def test_none_safe(self):
        # empty string; None would be a type error upstream but empty is common
        assert _normalize_domain("") == ""

    def test_whitespace(self):
        assert _normalize_domain("  rt.com  ") == "rt.com"

    def test_mixed_case(self):
        assert _normalize_domain("RT.COM") == "rt.com"

    def test_https_url(self):
        assert _normalize_domain("https://rt.com/article/123") == "rt.com"

    def test_http_url(self):
        assert _normalize_domain("http://rt.com/") == "rt.com"

    def test_www_prefix_stripped(self):
        assert _normalize_domain("www.rt.com") == "rt.com"

    def test_https_www_url(self):
        assert _normalize_domain("https://www.rt.com/") == "rt.com"

    def test_port_stripped(self):
        assert _normalize_domain("rt.com:443") == "rt.com"

    def test_trailing_dot_stripped(self):
        assert _normalize_domain("rt.com.") == "rt.com"

    def test_query_string_stripped(self):
        assert _normalize_domain("rt.com?utm_source=foo") == "rt.com"

    def test_fragment_stripped(self):
        assert _normalize_domain("rt.com#section") == "rt.com"

    def test_path_stripped(self):
        assert _normalize_domain("rt.com/article/2024") == "rt.com"

    def test_google_news_path(self):
        # Known limitation: google news redirects can't be unwrapped here
        # but the normalization should still return news.google.com
        assert _normalize_domain(
            "https://news.google.com/rss/articles/CBMi"
        ) == "news.google.com"

    def test_userinfo_stripped(self):
        assert _normalize_domain("https://user:pass@rt.com/") == "rt.com"

    def test_userinfo_no_password(self):
        assert _normalize_domain("https://user@rt.com/") == "rt.com"

    def test_double_dots_collapsed(self):
        assert _normalize_domain("rt..com") == "rt.com"

    def test_mobile_subdomain_preserved(self):
        # m.rt.com stays as m.rt.com at normalization level;
        # the get_outlet walk-up handles the lookup
        assert _normalize_domain("m.rt.com") == "m.rt.com"

    def test_english_subdomain_preserved(self):
        assert _normalize_domain("https://english.cgtn.com/article") == "english.cgtn.com"

    def test_real_gdelt_url_1(self):
        assert _normalize_domain(
            "https://www.tass.com/world/1234567"
        ) == "tass.com"

    def test_real_gdelt_url_2(self):
        assert _normalize_domain(
            "http://www.cctv.com:80/news/?id=1&utm_source=rss"
        ) == "cctv.com"

    def test_complex_real_world_url(self):
        assert _normalize_domain(
            "https://user:pass@www.english.cgtn.com:443/2024/article#comments"
        ) == "english.cgtn.com"

    def test_at_in_path_not_userinfo(self):
        # @ after the first slash is part of the path, not userinfo
        result = _normalize_domain("rt.com/user@name")
        assert result == "rt.com"


class TestGetOutletLookup:
    """Post-normalization, the subdomain walk-up must find parent outlets."""

    def test_bare_outlet_match(self):
        # rt.com should be a known outlet
        record = get_outlet("rt.com")
        assert record is not None
        assert record.country == "RU"

    def test_url_form_resolves_to_outlet(self):
        record = get_outlet("https://rt.com/article/123")
        assert record is not None
        assert record.country == "RU"

    def test_www_resolves_to_outlet(self):
        record = get_outlet("www.rt.com")
        assert record is not None
        assert record.country == "RU"

    def test_mobile_subdomain_parent_walkup(self):
        # m.rt.com should walk up to rt.com
        record = get_outlet("m.rt.com")
        assert record is not None
        assert record.country == "RU"

    def test_english_subdomain_parent_walkup(self):
        # english.cgtn.com should walk up to cgtn.com
        record = get_outlet("english.cgtn.com")
        assert record is not None
        assert record.country == "CN"

    def test_unknown_domain_returns_none(self):
        assert get_outlet("totally-unknown-site-12345.xyz") is None

    def test_empty_string_returns_none(self):
        assert get_outlet("") is None

    def test_full_url_with_tracking(self):
        record = get_outlet("https://www.rt.com/?utm_source=twitter&utm_medium=social")
        assert record is not None
        assert record.country == "RU"

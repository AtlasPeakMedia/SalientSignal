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


class TestSubdomainAudienceOverrides:
    """Regression: specific subdomain entries must beat parent-domain walk-up.

    The lookup in get_outlet() tries the full normalized hostname first, THEN
    walks up. So adding a more-specific subdomain entry to outlets.json is all
    it takes to override the parent's audience classification — no code change.

    These tests pin the Post-Phase-4 behavior observed in the real Supabase
    data, where foreign-language editions of Chinese state media were
    incorrectly rolling up to the DOMESTIC parent.
    """

    def test_russian_rt_is_domestic_not_international(self):
        # Parent rt.com is INTERNATIONAL; russian.rt.com serves Russian-speakers
        # so it should resolve as DOMESTIC, not walk up to INTERNATIONAL.
        record = get_outlet("russian.rt.com")
        assert record is not None
        assert record.audience_type == "DOMESTIC"
        assert record.country == "RU"

    def test_french_xinhuanet_is_international_not_domestic(self):
        # Parent xinhuanet.com is DOMESTIC; French edition targets foreign
        # audiences and should override to INTERNATIONAL.
        record = get_outlet("french.xinhuanet.com")
        assert record is not None
        assert record.audience_type == "INTERNATIONAL"
        assert record.country == "CN"
        assert "fr" in record.languages

    def test_arabic_xinhuanet_is_international(self):
        record = get_outlet("arabic.xinhuanet.com")
        assert record is not None
        assert record.audience_type == "INTERNATIONAL"
        assert "ar" in record.languages

    def test_japanese_xinhuanet_is_international(self):
        record = get_outlet("japanese.xinhuanet.com")
        assert record is not None
        assert record.audience_type == "INTERNATIONAL"
        assert "ja" in record.languages

    def test_russian_xinhuanet_is_international(self):
        record = get_outlet("russian.xinhuanet.com")
        assert record is not None
        assert record.audience_type == "INTERNATIONAL"
        assert "ru" in record.languages

    def test_spanish_xinhuanet_is_international(self):
        record = get_outlet("spanish.xinhuanet.com")
        assert record is not None
        assert record.audience_type == "INTERNATIONAL"
        assert "es" in record.languages

    def test_xinhua_news_cn_language_editions_are_international(self):
        # Parent news.cn is DOMESTIC; language editions are INTERNATIONAL.
        for subdomain, lang in [
            ("french.news.cn", "fr"),
            ("arabic.news.cn", "ar"),
            ("russian.news.cn", "ru"),
            ("japanese.news.cn", "ja"),
            ("portuguese.news.cn", "pt"),
        ]:
            record = get_outlet(subdomain)
            assert record is not None, f"{subdomain} not found"
            assert record.audience_type == "INTERNATIONAL", f"{subdomain} audience"
            assert lang in record.languages, f"{subdomain} language"

    def test_deutsch_rt_reclassified_international(self):
        # Was previously DIASPORA, which was a judgement error — RT DE is
        # explicitly outward-facing German-language propaganda and belongs
        # in the same INTERNATIONAL bucket as arabic.rt.com and francais.rt.com.
        record = get_outlet("deutsch.rt.com")
        assert record is not None
        assert record.audience_type == "INTERNATIONAL"

    def test_parent_domains_unchanged_by_overrides(self):
        # Regression guard: the DOMESTIC parent entries must still be DOMESTIC.
        # If someone ever accidentally flips these, every Chinese subdomain
        # walk-up changes behavior for sites we haven't registered explicitly.
        assert get_outlet("xinhuanet.com").audience_type == "DOMESTIC"
        assert get_outlet("news.cn").audience_type == "DOMESTIC"
        assert get_outlet("people.com.cn").audience_type == "DOMESTIC"
        assert get_outlet("cctv.com").audience_type == "DOMESTIC"
        assert get_outlet("rt.com").audience_type == "INTERNATIONAL"

    def test_unregistered_subdomain_still_walks_up(self):
        # edu.people.com.cn isn't explicitly registered — it should walk up
        # to people.com.cn → DOMESTIC. Confirms the override pattern doesn't
        # break the fallback walk-up for entries without a specific override.
        record = get_outlet("edu.people.com.cn")
        assert record is not None
        assert record.audience_type == "DOMESTIC"
        assert record.country == "CN"

    def test_regional_chinadaily_walks_up_to_international(self):
        # africa.chinadaily.com.cn has no explicit entry; parent chinadaily.com.cn
        # is already INTERNATIONAL, so walk-up gives us the right answer for free.
        for subdomain in (
            "africa.chinadaily.com.cn",
            "europe.chinadaily.com.cn",
            "usa.chinadaily.com.cn",
            "asia.chinadaily.com.cn",
        ):
            record = get_outlet(subdomain)
            assert record is not None, f"{subdomain} missing"
            assert record.audience_type == "INTERNATIONAL", f"{subdomain} bucket"
            assert record.country == "CN"


class TestTier2CountryCoverage:
    """B8 expansion: verify minimum outlet coverage for locked-down + Tier 2
    countries. These are the countries where 2-4 outlets are not enough to
    validate coordination or run meaningful baselines, so the B8 outlet
    expansion commits explicit floors per country.

    If any of these fail after future edits, either restore the missing
    outlet or update the floor AND update this test + the B8 commit rationale.
    """

    # Map of ISO2 -> minimum number of registered outlets required.
    # Floors are set low enough to allow pruning individual bad entries
    # without breaking the test, but high enough to catch accidental removals.
    TIER2_COVERAGE_FLOORS = {
        "IR": 15,  # Iran — locked-down, expanded to 21
        "KP": 6,   # DPRK — locked-down, expanded to 8
        "CU": 6,   # Cuba — locked-down, expanded to 9
        "BY": 5,   # Belarus — locked-down, expanded to 7
        "VE": 5,   # Venezuela — locked-down, expanded to 7
        "SY": 3,   # Syria — limited press freedom
        "SA": 6,   # Saudi Arabia — Gulf, expanded to 9
        "AE": 5,   # UAE — Gulf, expanded to 7
        "QA": 6,   # Qatar — Gulf, expanded to 8
        "TR": 8,   # Turkey — expanded to 11
        "RU": 20,  # Russia — Tier 1 core, expanded to 24
        "CN": 30,  # China — Tier 1 core, expanded to 34
        "ZW": 5,   # Zimbabwe — new in B8
        "AO": 3,   # Angola — new in B8
        "MZ": 3,   # Mozambique — new in B8
    }

    def test_tier2_coverage_floors_met(self):
        from src.outlets import get_all_outlets

        from collections import Counter
        countries = Counter(o.country for o in get_all_outlets())
        failures = []
        for iso2, floor in self.TIER2_COVERAGE_FLOORS.items():
            actual = countries.get(iso2, 0)
            if actual < floor:
                failures.append(f"{iso2}: {actual} outlets (floor {floor})")
        assert not failures, (
            "Tier 2 country coverage below floor — did B8 additions get "
            f"reverted?\n  " + "\n  ".join(failures)
        )

    def test_total_outlet_count_above_300(self):
        """B8 expansion target: 172 -> 300+. Regression guard."""
        from src.outlets import get_all_outlets
        assert len(get_all_outlets()) >= 300

    def test_minimum_country_coverage(self):
        """B8 added entries for 11 new countries (ZW, AO, MZ, TZ, RW, ZM, UG,
        ML, BF, SN, GH). Total monitored country count should be >= 80."""
        from src.outlets import get_monitored_countries
        assert len(get_monitored_countries()) >= 80

    def test_new_tier2_countries_represented(self):
        """Every new country added by B8 must have at least one outlet."""
        from src.outlets import get_monitored_countries
        monitored = get_monitored_countries()
        new_countries = {"ZW", "AO", "MZ", "TZ", "RW", "ZM", "UG", "ML", "BF", "SN", "GH"}
        missing = new_countries - monitored
        assert not missing, f"New B8 countries missing from outlets.json: {missing}"

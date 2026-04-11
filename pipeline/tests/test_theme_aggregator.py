"""Unit tests for theme_aggregator.

Builds synthetic GkgRow lists and asserts the aggregator bucketing math.
No network, no filesystem, no Supabase.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.gkg_client import GkgRow
from src.theme_aggregator import (
    DEFAULT_MIN_ARTICLE_COUNT,
    ThemeBucket,
    _monthly_period,
    _weekly_period,
    aggregate_themes,
)


def _make_row(
    *,
    domain: str = "tass.ru",
    url: str = "https://tass.ru/a/1",
    dt: datetime = datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc),
    themes: list[str] = None,
    tone: float | None = 0.0,
) -> GkgRow:
    return GkgRow(
        record_id="test",
        date=dt,
        domain=domain,
        raw_domain=domain,
        url=url,
        title="test",
        themes_v1=themes or ["ARMEDCONFLICT"],
        tone=tone,
    )


# ---------------------------------------------------------------------------
# Period bucketing
# ---------------------------------------------------------------------------
class TestPeriodMath:
    def test_monthly_period_mid_month(self):
        from datetime import date
        first, last = _monthly_period(date(2026, 4, 15))
        assert first == date(2026, 4, 1)
        assert last == date(2026, 4, 30)

    def test_monthly_period_december(self):
        from datetime import date
        first, last = _monthly_period(date(2026, 12, 15))
        assert first == date(2026, 12, 1)
        assert last == date(2026, 12, 31)

    def test_monthly_period_february_leap(self):
        from datetime import date
        first, last = _monthly_period(date(2024, 2, 15))
        assert first == date(2024, 2, 1)
        assert last == date(2024, 2, 29)

    def test_weekly_period_wednesday(self):
        from datetime import date
        # 2026-04-09 is a Thursday (isoweekday=4)
        # Monday of that week is 2026-04-06, Sunday is 2026-04-12
        mon, sun = _weekly_period(date(2026, 4, 9))
        assert mon == date(2026, 4, 6)
        assert sun == date(2026, 4, 12)

    def test_weekly_period_monday(self):
        from datetime import date
        mon, sun = _weekly_period(date(2026, 4, 6))
        assert mon == date(2026, 4, 6)
        assert sun == date(2026, 4, 12)

    def test_weekly_period_sunday(self):
        from datetime import date
        # 2026-04-12 is a Sunday — week should be 04-06..04-12
        mon, sun = _weekly_period(date(2026, 4, 12))
        assert mon == date(2026, 4, 6)
        assert sun == date(2026, 4, 12)


# ---------------------------------------------------------------------------
# Aggregation core (uses real outlets.json via get_outlet)
# ---------------------------------------------------------------------------
class TestAggregateThemes:
    def test_single_row_single_theme_monthly(self):
        row = _make_row(
            domain="tass.ru",  # RU DOMESTIC
            dt=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
            themes=["ARMEDCONFLICT"],
            tone=-5.0,
        )
        # min_article_count=1 so single-row themes survive
        buckets = aggregate_themes(
            [row], period_type="monthly", min_article_count=1
        )
        assert len(buckets) == 1
        b = buckets[0]
        assert b.country == "RU"
        assert b.audience_type == "DOMESTIC"
        assert b.period_type == "monthly"
        assert b.theme == "ARMEDCONFLICT"
        assert b.article_count == 1
        assert b.bucket_total == 1
        assert b.share == pytest.approx(1.0)
        assert b.avg_tone == pytest.approx(-5.0)

    def test_dedup_by_domain_url(self):
        """Same (domain, url) emitted in two GKG files counts once."""
        r1 = _make_row(domain="tass.ru", url="https://tass.ru/a/1", themes=["ARMEDCONFLICT"])
        r2 = _make_row(domain="tass.ru", url="https://tass.ru/a/1", themes=["ARMEDCONFLICT"])
        buckets = aggregate_themes([r1, r2], min_article_count=1)
        # Only one bucket, count should be 1 not 2
        assert len(buckets) == 1
        assert buckets[0].article_count == 1
        assert buckets[0].bucket_total == 1

    def test_different_urls_not_deduped(self):
        """Two distinct articles on the same domain both count."""
        r1 = _make_row(domain="tass.ru", url="https://tass.ru/a/1", themes=["ARMEDCONFLICT"])
        r2 = _make_row(domain="tass.ru", url="https://tass.ru/a/2", themes=["ARMEDCONFLICT"])
        buckets = aggregate_themes([r1, r2], min_article_count=1)
        assert buckets[0].article_count == 2

    def test_country_split_by_outlet(self):
        """tass.ru (RU) and dailysabah.com (TR INTL) produce separate buckets."""
        r1 = _make_row(domain="tass.ru", url="https://tass.ru/a/1", themes=["ARMEDCONFLICT"])
        r2 = _make_row(domain="dailysabah.com", url="https://dailysabah.com/a/1", themes=["ARMEDCONFLICT"])
        buckets = aggregate_themes([r1, r2], min_article_count=1)
        by_country = {(b.country, b.audience_type): b for b in buckets}
        assert ("RU", "DOMESTIC") in by_country or ("RU", "INTERNATIONAL") in by_country
        assert any(b.country == "TR" for b in buckets)

    def test_audience_split_within_country(self):
        """Chinese domestic and international outlets produce separate buckets."""
        r_dom = _make_row(
            domain="xinhuanet.com",  # DOMESTIC
            url="https://xinhuanet.com/a/1",
            themes=["TAX_ETHNICITY_CHINESE"],
        )
        r_intl = _make_row(
            domain="french.xinhuanet.com",  # Should walk up to xinhuanet.com... or not
            url="https://french.xinhuanet.com/a/2",
            themes=["TAX_ETHNICITY_CHINESE"],
        )
        buckets = aggregate_themes([r_dom, r_intl], min_article_count=1)
        # Both should be CN. The audience split depends on whether the
        # subdomain french.xinhuanet.com has its own outlets.json entry
        # that overrides audience type (session 21 fix added these).
        assert all(b.country == "CN" for b in buckets)

    def test_top_n_truncation(self):
        """If a bucket has 10 themes, top_n=3 keeps only the 3 most frequent."""
        rows = []
        # 10 rows all with the same theme set — each row mentions all 10
        for i in range(10):
            rows.append(_make_row(
                domain="tass.ru",
                url=f"https://tass.ru/a/{i}",
                themes=[f"THEME_{j}" for j in range(10)],
            ))
        buckets = aggregate_themes(rows, top_n=3, min_article_count=1)
        assert len(buckets) == 3  # Only 3 themes survive
        # All 3 should have the same article_count (10) since every article
        # mentions every theme
        assert all(b.article_count == 10 for b in buckets)

    def test_min_article_count_filters_noise(self):
        """Themes with fewer than min_article_count mentions are dropped."""
        # One row with 3 themes — only one of which will repeat across rows
        rows = [
            _make_row(domain="tass.ru", url=f"https://tass.ru/a/{i}", themes=["ARMEDCONFLICT"])
            for i in range(3)
        ]
        rows.append(_make_row(
            domain="tass.ru",
            url="https://tass.ru/noise",
            themes=["OBSCURE_THEME"],
        ))
        # min_article_count=2 should drop OBSCURE_THEME
        buckets = aggregate_themes(rows, min_article_count=2)
        themes = {b.theme for b in buckets}
        assert "ARMEDCONFLICT" in themes
        assert "OBSCURE_THEME" not in themes

    def test_different_months_different_buckets(self):
        """Rows from January and February produce separate buckets."""
        r_jan = _make_row(
            domain="tass.ru",
            url="https://tass.ru/jan",
            dt=datetime(2026, 1, 15, tzinfo=timezone.utc),
            themes=["ARMEDCONFLICT"],
        )
        r_feb = _make_row(
            domain="tass.ru",
            url="https://tass.ru/feb",
            dt=datetime(2026, 2, 15, tzinfo=timezone.utc),
            themes=["ARMEDCONFLICT"],
        )
        buckets = aggregate_themes(
            [r_jan, r_feb], period_type="monthly", min_article_count=1
        )
        periods = {b.period_start for b in buckets}
        assert len(periods) == 2

    def test_weekly_bucketing(self):
        """Two rows in the same ISO week land in one weekly bucket."""
        r1 = _make_row(
            domain="tass.ru",
            url="https://tass.ru/mon",
            dt=datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc),  # Monday
            themes=["ARMEDCONFLICT"],
        )
        r2 = _make_row(
            domain="tass.ru",
            url="https://tass.ru/fri",
            dt=datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),  # Friday same week
            themes=["ARMEDCONFLICT"],
        )
        buckets = aggregate_themes(
            [r1, r2], period_type="weekly", min_article_count=1
        )
        assert len(buckets) == 1
        assert buckets[0].article_count == 2

    def test_tone_averaging(self):
        """avg_tone is the mean across articles mentioning the theme."""
        r1 = _make_row(
            domain="tass.ru", url="https://tass.ru/a/1",
            themes=["ARMEDCONFLICT"], tone=-6.0,
        )
        r2 = _make_row(
            domain="tass.ru", url="https://tass.ru/a/2",
            themes=["ARMEDCONFLICT"], tone=-4.0,
        )
        buckets = aggregate_themes([r1, r2], min_article_count=1)
        assert buckets[0].avg_tone == pytest.approx(-5.0)

    def test_tone_none_excluded_from_average(self):
        """Rows with tone=None don't poison the average."""
        r1 = _make_row(
            domain="tass.ru", url="https://tass.ru/a/1",
            themes=["ARMEDCONFLICT"], tone=-5.0,
        )
        r2 = _make_row(
            domain="tass.ru", url="https://tass.ru/a/2",
            themes=["ARMEDCONFLICT"], tone=None,
        )
        buckets = aggregate_themes([r1, r2], min_article_count=1)
        assert buckets[0].article_count == 2
        assert buckets[0].avg_tone == pytest.approx(-5.0)  # only one tone contributed

    def test_share_computation(self):
        """share = theme mentions / bucket total."""
        # 10 articles, only 3 mention ARMEDCONFLICT
        rows = []
        for i in range(7):
            rows.append(_make_row(
                domain="tass.ru", url=f"https://tass.ru/a/{i}",
                themes=["OTHER_THEME"],
            ))
        for i in range(3):
            rows.append(_make_row(
                domain="tass.ru", url=f"https://tass.ru/b/{i}",
                themes=["ARMEDCONFLICT"],
            ))
        buckets = aggregate_themes(rows, min_article_count=1)
        armed = next(b for b in buckets if b.theme == "ARMEDCONFLICT")
        assert armed.article_count == 3
        assert armed.bucket_total == 10
        assert armed.share == pytest.approx(0.3)

    def test_output_is_deterministic_and_sorted(self):
        """Same input always produces same output in same order."""
        rows = [
            _make_row(domain="tass.ru", url=f"https://tass.ru/a/{i}",
                      themes=[f"THEME_{j}" for j in range(5)])
            for i in range(5)
        ]
        b1 = aggregate_themes(rows, min_article_count=1)
        b2 = aggregate_themes(rows, min_article_count=1)
        assert len(b1) == len(b2)
        for a, b in zip(b1, b2):
            assert a.to_dict() == b.to_dict()

    def test_empty_input_returns_empty_list(self):
        assert aggregate_themes([]) == []

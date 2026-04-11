"""Unit tests for import_gkg_backfill.py validation passes.

The import script's job is to reject bad data before it reaches
production Supabase. Every validation pass must be exercised here because
the downstream upsert has no fallback — a bad row at this layer becomes
a corrupt row in the country_theme_monthly table.

No network, no Supabase — we import the script's validator functions
directly and feed them synthetic buckets.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Mirror the test_run_backfill_cli.py pattern: put scripts/ + pipeline/
# on sys.path so we can import the script by its bare module name.
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
PIPELINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(PIPELINE_DIR))

import import_gkg_backfill  # noqa: E402


def _make_bucket(**overrides) -> dict:
    """Produce a valid bucket dict that passes every validation pass.
    Individual tests override a specific field to exercise a specific
    failure mode."""
    base = {
        "country": "RU",
        "audience_type": "DOMESTIC",
        "period_type": "monthly",
        "period_start": "2026-04-01",
        "period_end": "2026-04-30",
        "theme": "ARMEDCONFLICT",
        "article_count": 42,
        "bucket_total": 100,
        "share": 0.42,
        "avg_tone": -3.5,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Pass 1: schema shape
# ---------------------------------------------------------------------------
class TestValidateShape:
    def test_valid_bucket_passes(self):
        import_gkg_backfill._validate_shape([_make_bucket()])

    def test_missing_country_raises(self):
        bad = _make_bucket()
        del bad["country"]
        with pytest.raises(SystemExit, match="missing keys"):
            import_gkg_backfill._validate_shape([bad])

    def test_missing_theme_raises(self):
        bad = _make_bucket()
        del bad["theme"]
        with pytest.raises(SystemExit, match="missing keys"):
            import_gkg_backfill._validate_shape([bad])

    def test_missing_multiple_keys_raises(self):
        bad = _make_bucket()
        del bad["article_count"]
        del bad["share"]
        with pytest.raises(SystemExit, match="missing keys"):
            import_gkg_backfill._validate_shape([bad])

    def test_empty_list_is_fine(self):
        # No rows, no required keys to check — nothing should raise
        import_gkg_backfill._validate_shape([])


# ---------------------------------------------------------------------------
# Pass 2: value ranges
# ---------------------------------------------------------------------------
class TestValidateValueRanges:
    def test_valid_bucket_passes(self):
        import_gkg_backfill._validate_value_ranges([_make_bucket()])

    def test_invalid_audience_raises(self):
        bad = _make_bucket(audience_type="NEUTRAL")
        with pytest.raises(SystemExit, match="invalid audience_type"):
            import_gkg_backfill._validate_value_ranges([bad])

    def test_negative_article_count_raises(self):
        bad = _make_bucket(article_count=-5)
        with pytest.raises(SystemExit, match="negative count"):
            import_gkg_backfill._validate_value_ranges([bad])

    def test_negative_bucket_total_raises(self):
        bad = _make_bucket(bucket_total=-1)
        with pytest.raises(SystemExit, match="negative count"):
            import_gkg_backfill._validate_value_ranges([bad])

    def test_share_above_1_raises(self):
        bad = _make_bucket(share=1.5)
        with pytest.raises(SystemExit, match="share out of"):
            import_gkg_backfill._validate_value_ranges([bad])

    def test_share_below_0_raises(self):
        bad = _make_bucket(share=-0.1)
        with pytest.raises(SystemExit, match="share out of"):
            import_gkg_backfill._validate_value_ranges([bad])

    def test_share_exactly_0_ok(self):
        # Edge case — share can be 0 for filtered-out themes; no exception
        import_gkg_backfill._validate_value_ranges([_make_bucket(share=0.0)])

    def test_share_exactly_1_ok(self):
        # Edge case — share can be 1.0 if every article mentions the theme
        import_gkg_backfill._validate_value_ranges([_make_bucket(share=1.0)])

    def test_malformed_date_raises(self):
        bad = _make_bucket(period_start="not-a-date")
        with pytest.raises(SystemExit, match="bad date format"):
            import_gkg_backfill._validate_value_ranges([bad])

    def test_period_end_before_start_raises(self):
        bad = _make_bucket(period_start="2026-04-30", period_end="2026-04-01")
        with pytest.raises(SystemExit, match="period_end .* before period_start"):
            import_gkg_backfill._validate_value_ranges([bad])

    def test_diaspora_is_valid_audience(self):
        # DIASPORA is the third valid audience type; should pass
        import_gkg_backfill._validate_value_ranges([_make_bucket(audience_type="DIASPORA")])


# ---------------------------------------------------------------------------
# Pass 3: volume ceiling
# ---------------------------------------------------------------------------
class TestValidateVolume:
    def test_small_dataset_passes(self):
        import_gkg_backfill._validate_volume([_make_bucket() for _ in range(100)])

    def test_empty_list_passes(self):
        import_gkg_backfill._validate_volume([])

    def test_ceiling_enforced(self, monkeypatch):
        # Monkey-patch the ceiling down so we don't allocate 5M buckets
        monkeypatch.setattr(import_gkg_backfill, "MAX_BUCKETS", 10)
        with pytest.raises(SystemExit, match="exceeds safety ceiling"):
            import_gkg_backfill._validate_volume([_make_bucket() for _ in range(11)])


# ---------------------------------------------------------------------------
# Pass 4: date freshness (warn only, returns list)
# ---------------------------------------------------------------------------
class TestValidateDates:
    def test_current_date_no_warnings(self):
        # A bucket dated April 2025 is well in the past — no forward-date
        # warnings expected
        warnings = import_gkg_backfill._validate_dates([_make_bucket()])
        assert warnings == []

    def test_forward_dated_buckets_produce_warning(self):
        forward = _make_bucket(period_start="2030-01-01", period_end="2030-01-31")
        warnings = import_gkg_backfill._validate_dates([forward])
        assert len(warnings) == 1
        assert "forward-dated" in warnings[0] or "after today" in warnings[0]

    def test_mixed_past_and_forward_counts_only_forward(self):
        past = _make_bucket(period_start="2025-01-01", period_end="2025-01-31")
        forward1 = _make_bucket(period_start="2030-01-01", period_end="2030-01-31")
        forward2 = _make_bucket(period_start="2031-06-01", period_end="2031-06-30")
        warnings = import_gkg_backfill._validate_dates([past, forward1, forward2])
        assert len(warnings) == 1
        # The warning mentions 2 buckets, not 3
        assert "2" in warnings[0]


# ---------------------------------------------------------------------------
# Pass 5: FVEY exclusion
# ---------------------------------------------------------------------------
class TestValidateFvey:
    def test_clean_dataset_passes(self):
        import_gkg_backfill._validate_fvey([
            _make_bucket(country="RU"),
            _make_bucket(country="CN"),
            _make_bucket(country="IR"),
        ])

    def test_us_raises(self):
        bad = _make_bucket(country="US")
        with pytest.raises(SystemExit, match="FVEY rows leaked"):
            import_gkg_backfill._validate_fvey([bad])

    def test_gb_raises(self):
        bad = _make_bucket(country="GB")
        with pytest.raises(SystemExit, match="FVEY rows leaked"):
            import_gkg_backfill._validate_fvey([bad])

    def test_uk_alias_raises(self):
        # UK is in the FVEY set alongside GB as a safety fallback
        bad = _make_bucket(country="UK")
        with pytest.raises(SystemExit, match="FVEY rows leaked"):
            import_gkg_backfill._validate_fvey([bad])

    def test_lowercase_country_still_caught(self):
        """The validator uppercases before checking, so lowercase FVEY
        codes must still be rejected."""
        bad = _make_bucket(country="us")
        with pytest.raises(SystemExit, match="FVEY rows leaked"):
            import_gkg_backfill._validate_fvey([bad])

    def test_all_fvey_countries_rejected(self):
        for fvey_code in ("US", "GB", "UK", "CA", "AU", "NZ"):
            with pytest.raises(SystemExit, match="FVEY rows leaked"):
                import_gkg_backfill._validate_fvey([_make_bucket(country=fvey_code)])


# ---------------------------------------------------------------------------
# Pass 6: period consistency
# ---------------------------------------------------------------------------
class TestValidatePeriodConsistency:
    def test_monthly_day_1_passes(self):
        import_gkg_backfill._validate_period_consistency(
            [_make_bucket(period_start="2026-04-01")], "monthly",
        )

    def test_monthly_mid_month_raises(self):
        bad = _make_bucket(period_start="2026-04-15")
        with pytest.raises(SystemExit, match="monthly period_start .* is not day 1"):
            import_gkg_backfill._validate_period_consistency([bad], "monthly")

    def test_weekly_monday_passes(self):
        # 2026-04-06 is a Monday
        import_gkg_backfill._validate_period_consistency(
            [_make_bucket(period_start="2026-04-06", period_end="2026-04-12")],
            "weekly",
        )

    def test_weekly_tuesday_raises(self):
        # 2026-04-07 is a Tuesday
        bad = _make_bucket(period_start="2026-04-07", period_end="2026-04-13")
        with pytest.raises(SystemExit, match="weekly period_start .* is not a Monday"):
            import_gkg_backfill._validate_period_consistency([bad], "weekly")

    def test_weekly_sunday_raises(self):
        # 2026-04-12 is a Sunday — must be Monday
        bad = _make_bucket(period_start="2026-04-12", period_end="2026-04-18")
        with pytest.raises(SystemExit, match="weekly period_start .* is not a Monday"):
            import_gkg_backfill._validate_period_consistency([bad], "weekly")

    def test_daily_does_not_enforce_boundary(self):
        # Daily period can start on any day — no boundary check
        import_gkg_backfill._validate_period_consistency(
            [_make_bucket(period_start="2026-04-07", period_end="2026-04-07")],
            "daily",
        )

"""Tests for backfill.py — Phase A2 historical backfill aggregation.

Covers the A2 acceptance criteria:
  - Single outlet 30-day window produces the right row shape and count
  - Multiple outlets in same country + audience sum correctly
  - Multi-audience split keeps DOMESTIC and INTERNATIONAL separate
  - Baseline math uses ONLY preceding-window dates (no false zero padding)
  - resume_from skips earlier outlets alphabetically
  - Empty outlet (zero activity) increments stats.outlets_empty, not failures
  - One outlet raising an exception does NOT halt the run
  - End-to-end integration with InMemoryDb upsert
  - Row shape matches the live pipeline's country_activity schema
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.backfill import (
    BackfillResult,
    BackfillStats,
    run_backfill,
)
from src.db import InMemoryDb
from src.gdelt_timeline_client import TimelineResult, TimelineRow
from src.outlets import OutletRecord


# ---------------------------------------------------------------------------
# Helpers: synthetic outlets + fake timeline client
# ---------------------------------------------------------------------------
def _make_outlet(
    domain: str,
    country: str,
    audience_type: str = "DOMESTIC",
) -> OutletRecord:
    return OutletRecord(
        domain=domain,
        country=country,
        audience_type=audience_type,
        outlet_name=f"Test {domain}",
        outlet_type="news agency",
        languages=("en",),
        is_state_owned=True,
        is_state_aligned=False,
        confidence=1.0,
    )


def _timeline_result(
    domain: str,
    start_date: date,
    end_date: date,
    daily_volume: dict[date, int] | int,
) -> TimelineResult:
    """Build a synthetic TimelineResult.

    If ``daily_volume`` is an int, every day in the range gets that volume.
    If it's a dict, only the specified dates get volumes (missing dates
    return zero — matching the real client's behavior).
    """
    days = (end_date - start_date).days
    rows: list[TimelineRow] = []
    for i in range(days + 1):
        d = start_date + timedelta(days=i)
        if isinstance(daily_volume, dict):
            vol = daily_volume.get(d, 0)
            if vol == 0:
                continue  # real client doesn't emit zero rows
        else:
            vol = daily_volume
        rows.append(TimelineRow(date=d, volume_raw=vol, domain=domain))
    return TimelineResult(
        rows=rows,
        domain=domain,
        start_date=start_date,
        end_date=end_date,
        duration_seconds=0.01,
        retries=0,
    )


class FakeTimelineClient:
    """Injectable timeline client for tests. Records every call."""

    def __init__(self, response_for: dict[str, dict[date, int] | int] | None = None):
        # Map domain -> daily volume spec
        self.response_for = response_for or {}
        self.calls: list[tuple[str, date, date]] = []

    def __call__(
        self,
        domain: str,
        *,
        start_date: date,
        end_date: date,
        **_kwargs,
    ) -> TimelineResult:
        self.calls.append((domain, start_date, end_date))
        spec = self.response_for.get(domain)
        if spec is None:
            # Default: empty (silent outlet)
            return TimelineResult(
                rows=[],
                domain=domain,
                start_date=start_date,
                end_date=end_date,
                duration_seconds=0.01,
            )
        return _timeline_result(domain, start_date, end_date, spec)


class RaisingTimelineClient:
    """Timeline client that raises for specific domains, succeeds for others."""

    def __init__(
        self,
        raise_for: set[str],
        exc: Exception,
        fallback_volume: int = 5,
    ):
        self.raise_for = raise_for
        self.exc = exc
        self.fallback_volume = fallback_volume
        self.calls: list[str] = []

    def __call__(
        self,
        domain: str,
        *,
        start_date: date,
        end_date: date,
        **_kwargs,
    ) -> TimelineResult:
        self.calls.append(domain)
        if domain in self.raise_for:
            raise self.exc
        return _timeline_result(domain, start_date, end_date, self.fallback_volume)


# ---------------------------------------------------------------------------
# 1. Single outlet 30-day window
# ---------------------------------------------------------------------------
class TestSingleOutlet:
    def test_single_outlet_30_days_produces_30_rows(self):
        outlet = _make_outlet("tass.ru", "RU", "DOMESTIC")
        client = FakeTimelineClient(response_for={"tass.ru": 10})  # 10/day

        result = run_backfill(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 30),
            outlets=[outlet],
            timeline_client=client,
        )

        assert isinstance(result, BackfillResult)
        assert result.stats.outlets_queried == 1
        assert result.stats.outlets_succeeded == 1
        assert result.stats.outlets_failed == 0
        assert result.stats.days_covered == 30
        # 1 bucket (RU/DOMESTIC) × 30 days = 30 rows
        assert result.stats.country_activity_rows == 30
        assert len(result.country_activity) == 30

    def test_single_outlet_row_shape_matches_live_pipeline(self):
        """The row dict must have the exact same keys as pipeline.py emits."""
        outlet = _make_outlet("rt.com", "RU", "INTERNATIONAL")
        client = FakeTimelineClient(response_for={"rt.com": 5})

        result = run_backfill(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 10),
            outlets=[outlet],
            timeline_client=client,
        )

        row = result.country_activity[0]
        expected_keys = {
            "country",
            "date",
            "audience_type",
            "today_count",
            "baseline_mean",
            "baseline_std",
            "deviation_ratio",
            "z_score",
            "level",
            "confidence",
            "cold_start",
            "top_themes",
            "top_outlets",
        }
        assert set(row.keys()) == expected_keys
        assert row["country"] == "RU"
        assert row["audience_type"] == "INTERNATIONAL"
        assert row["today_count"] == 5
        assert row["top_themes"] == {}  # backfill has no themes
        assert row["top_outlets"] == [{"domain": "rt.com", "count": 5}]
        assert row["date"] == "2025-01-01"


# ---------------------------------------------------------------------------
# 2. Multi-outlet same country: counts should be summed
# ---------------------------------------------------------------------------
class TestMultiOutletAggregation:
    def test_three_domestic_ru_outlets_sum_correctly(self):
        outlets = [
            _make_outlet("tass.ru", "RU", "DOMESTIC"),
            _make_outlet("ria.ru", "RU", "DOMESTIC"),
            _make_outlet("rossiya1.ru", "RU", "DOMESTIC"),
        ]
        client = FakeTimelineClient(
            response_for={
                "tass.ru": 10,
                "ria.ru": 20,
                "rossiya1.ru": 30,
            }
        )

        result = run_backfill(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
            outlets=outlets,
            timeline_client=client,
        )

        # 1 bucket (RU/DOMESTIC) × 5 days = 5 rows
        assert len(result.country_activity) == 5
        for row in result.country_activity:
            assert row["country"] == "RU"
            assert row["audience_type"] == "DOMESTIC"
            assert row["today_count"] == 60  # 10 + 20 + 30
            # top_outlets should be sorted by count desc
            assert row["top_outlets"][0]["domain"] == "rossiya1.ru"
            assert row["top_outlets"][0]["count"] == 30
            assert row["top_outlets"][1]["domain"] == "ria.ru"
            assert row["top_outlets"][2]["domain"] == "tass.ru"


# ---------------------------------------------------------------------------
# 3. Multi-audience: DOMESTIC and INTERNATIONAL stay separate
# ---------------------------------------------------------------------------
class TestMultiAudienceSplit:
    def test_domestic_and_international_stay_separate(self):
        outlets = [
            _make_outlet("tass.ru", "RU", "DOMESTIC"),
            _make_outlet("rt.com", "RU", "INTERNATIONAL"),
            _make_outlet("sputniknews.com", "RU", "INTERNATIONAL"),
        ]
        client = FakeTimelineClient(
            response_for={
                "tass.ru": 100,
                "rt.com": 25,
                "sputniknews.com": 15,
            }
        )

        result = run_backfill(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 3),
            outlets=outlets,
            timeline_client=client,
        )

        # 2 buckets (RU/DOMESTIC, RU/INTERNATIONAL) × 3 days = 6 rows
        assert len(result.country_activity) == 6

        domestic_rows = [
            r for r in result.country_activity if r["audience_type"] == "DOMESTIC"
        ]
        international_rows = [
            r for r in result.country_activity if r["audience_type"] == "INTERNATIONAL"
        ]

        assert len(domestic_rows) == 3
        assert len(international_rows) == 3
        assert all(r["today_count"] == 100 for r in domestic_rows)
        assert all(r["today_count"] == 40 for r in international_rows)  # 25 + 15


# ---------------------------------------------------------------------------
# 4. Baseline math: only the preceding window contributes
# ---------------------------------------------------------------------------
class TestBaselineMath:
    def test_baseline_uses_only_preceding_days_inside_window(self):
        """For target_date == start_date, no preceding data exists → Baseline.empty().
        For target_date == start_date + 30, exactly 30 preceding days exist.
        """
        outlet = _make_outlet("steady.ru", "RU", "DOMESTIC")
        # 10 articles per day, every day
        client = FakeTimelineClient(response_for={"steady.ru": 10})

        result = run_backfill(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 2, 14),  # 45 days
            outlets=[outlet],
            timeline_client=client,
        )

        rows_by_date = {row["date"]: row for row in result.country_activity}

        # Day 1 (Jan 1): no preceding data → baseline.empty, cold_start True
        row_day1 = rows_by_date["2025-01-01"]
        assert row_day1["cold_start"] is True
        assert row_day1["baseline_mean"] == 0.0
        assert row_day1["confidence"] == "LOW"

        # Day 10 (Jan 10): 9 preceding days → cold_start False (>=7), MEDIUM confidence
        row_day10 = rows_by_date["2025-01-10"]
        assert row_day10["cold_start"] is False
        assert row_day10["baseline_mean"] == 10.0  # steady 10/day
        assert row_day10["confidence"] == "MEDIUM"

        # Day 31 (Jan 31): 30 preceding days → HIGH confidence, stable baseline
        row_day31 = rows_by_date["2025-01-31"]
        assert row_day31["cold_start"] is False
        assert row_day31["baseline_mean"] == 10.0
        assert row_day31["baseline_std"] == 0.0  # perfect consistency
        assert row_day31["confidence"] == "HIGH"

    def test_baseline_does_not_pad_with_pre_window_zeros(self):
        """Regression: if the window is [Jan 1, Jan 30] and baseline asks for
        Dec 2-31, those dates are OUTSIDE the window and must NOT be padded
        with zeros. Day 1's baseline should be empty, not a fake 30 zeros."""
        outlet = _make_outlet("steady.ru", "RU", "DOMESTIC")
        client = FakeTimelineClient(response_for={"steady.ru": 10})

        result = run_backfill(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 30),
            outlets=[outlet],
            timeline_client=client,
        )

        row_day1 = result.country_activity[0]
        # Day 1 should have days_sampled=0 (empty baseline), not days_sampled=30 w/ mean=0
        # Evidenced by: confidence=LOW and cold_start=True
        assert row_day1["cold_start"] is True
        assert row_day1["confidence"] == "LOW"
        assert row_day1["baseline_mean"] == 0.0
        # The deviation ratio should NOT be treated as a spike from zero-mean
        assert row_day1["level"] == "neutral"  # Baseline.empty → neutral


# ---------------------------------------------------------------------------
# 5. resume_from: skip earlier outlets alphabetically
# ---------------------------------------------------------------------------
class TestResumeFrom:
    def test_resume_from_skips_strictly_earlier_outlets(self):
        outlets = [
            _make_outlet("apple.ru", "RU", "DOMESTIC"),
            _make_outlet("banana.ru", "RU", "DOMESTIC"),
            _make_outlet("cherry.ru", "RU", "DOMESTIC"),
            _make_outlet("date.ru", "RU", "DOMESTIC"),
        ]
        client = FakeTimelineClient(response_for={o.domain: 10 for o in outlets})

        result = run_backfill(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 3),
            outlets=outlets,
            timeline_client=client,
            resume_from="cherry.ru",
        )

        # apple.ru and banana.ru should be skipped; cherry.ru and date.ru queried
        queried_domains = {call[0] for call in client.calls}
        assert queried_domains == {"cherry.ru", "date.ru"}
        assert result.stats.outlets_skipped == 2
        assert result.stats.outlets_queried == 2

    def test_no_resume_from_queries_everything(self):
        outlets = [
            _make_outlet("a.ru", "RU"),
            _make_outlet("b.ru", "RU"),
        ]
        client = FakeTimelineClient(response_for={"a.ru": 5, "b.ru": 7})

        result = run_backfill(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
            outlets=outlets,
            timeline_client=client,
        )

        assert result.stats.outlets_skipped == 0
        assert result.stats.outlets_queried == 2


# ---------------------------------------------------------------------------
# 6. Empty outlet (no activity) is counted separately from failures
# ---------------------------------------------------------------------------
class TestEmptyOutlets:
    def test_empty_outlet_counted_as_empty_not_failed(self):
        outlets = [
            _make_outlet("active.ru", "RU"),
            _make_outlet("silent.ru", "RU"),
        ]
        # silent.ru has no response_for entry → client returns empty TimelineResult
        client = FakeTimelineClient(response_for={"active.ru": 15})

        result = run_backfill(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
            outlets=outlets,
            timeline_client=client,
        )

        assert result.stats.outlets_succeeded == 2
        assert result.stats.outlets_empty == 1  # silent.ru
        assert result.stats.outlets_failed == 0
        assert len(result.failures) == 0

        # active.ru's counts still flow through; silent.ru contributes 0
        for row in result.country_activity:
            assert row["today_count"] == 15


# ---------------------------------------------------------------------------
# 7. Failing outlet does not halt the run
# ---------------------------------------------------------------------------
class TestFailureResilience:
    def test_one_outlet_raising_does_not_halt_others(self):
        outlets = [
            _make_outlet("good1.ru", "RU"),
            _make_outlet("broken.ru", "RU"),
            _make_outlet("good2.ru", "RU"),
        ]
        client = RaisingTimelineClient(
            raise_for={"broken.ru"},
            exc=RuntimeError("GDELT returned garbage"),
            fallback_volume=8,
        )

        result = run_backfill(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 3),
            outlets=outlets,
            timeline_client=client,
        )

        assert result.stats.outlets_queried == 3
        assert result.stats.outlets_succeeded == 2
        assert result.stats.outlets_failed == 1
        assert len(result.failures) == 1
        assert result.failures[0][0] == "broken.ru"
        assert "garbage" in result.failures[0][1]

        # good1 + good2 contributions (8 each) = 16/day
        for row in result.country_activity:
            assert row["today_count"] == 16


# ---------------------------------------------------------------------------
# 8. End-to-end integration with InMemoryDb upsert
# ---------------------------------------------------------------------------
class TestInMemoryDbIntegration:
    def test_rows_upsert_to_inmemorydb_without_error(self):
        """The row shape must be compatible with the existing batch upsert."""
        outlet = _make_outlet("xinhua.cn", "CN", "DOMESTIC")
        client = FakeTimelineClient(response_for={"xinhua.cn": 42})

        result = run_backfill(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 2, 28),  # 59 days
            outlets=[outlet],
            timeline_client=client,
        )

        db = InMemoryDb()
        # Must not raise; must return the correct count
        inserted = db.upsert_country_activity_batch(result.country_activity)

        assert inserted == 59
        assert len(db.country_activity) == 59
        # Primary key (country, date, audience_type) uniqueness preserved
        unique_keys = {
            (r["country"], r["date"], r["audience_type"]) for r in db.country_activity
        }
        assert len(unique_keys) == 59

    def test_raw_outlet_daily_counts_preserved_for_audit(self):
        """BackfillResult should retain per-(domain, date) raw counts so
        import_backfill.py can audit any suspicious country_activity row."""
        outlets = [
            _make_outlet("a.ru", "RU"),
            _make_outlet("b.ru", "RU"),
        ]
        client = FakeTimelineClient(
            response_for={
                "a.ru": {date(2025, 1, 1): 7, date(2025, 1, 2): 11},
                "b.ru": {date(2025, 1, 1): 3},
            }
        )

        result = run_backfill(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 3),
            outlets=outlets,
            timeline_client=client,
        )

        assert result.raw_outlet_daily_counts[("a.ru", date(2025, 1, 1))] == 7
        assert result.raw_outlet_daily_counts[("a.ru", date(2025, 1, 2))] == 11
        assert result.raw_outlet_daily_counts[("b.ru", date(2025, 1, 1))] == 3
        # b.ru has no entry for Jan 2 → key absent (not zero)
        assert ("b.ru", date(2025, 1, 2)) not in result.raw_outlet_daily_counts


# ---------------------------------------------------------------------------
# Date validation
# ---------------------------------------------------------------------------
class TestDateValidation:
    def test_start_after_end_raises(self):
        with pytest.raises(ValueError, match="must be <="):
            run_backfill(
                start_date=date(2025, 6, 30),
                end_date=date(2025, 1, 1),
                outlets=[_make_outlet("x.ru", "RU")],
                timeline_client=FakeTimelineClient(),
            )

    def test_single_day_window(self):
        """start_date == end_date is a valid 1-day window."""
        outlet = _make_outlet("x.ru", "RU")
        client = FakeTimelineClient(response_for={"x.ru": 3})

        result = run_backfill(
            start_date=date(2025, 6, 15),
            end_date=date(2025, 6, 15),
            outlets=[outlet],
            timeline_client=client,
        )

        assert result.stats.days_covered == 1
        assert len(result.country_activity) == 1
        assert result.country_activity[0]["date"] == "2025-06-15"
        assert result.country_activity[0]["today_count"] == 3

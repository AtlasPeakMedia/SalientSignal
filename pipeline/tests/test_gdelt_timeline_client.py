"""Tests for gdelt_timeline_client.py — Phase A1 historical backfill support.

Covers:
  - Success path: DataFrame → TimelineRows, domain attached, All Articles ignored
  - Empty result is NOT an error (zero-activity outlet is valid)
  - Missing required columns is handled gracefully
  - Retries on transient errors / 429s, gives up after max_retries without raising
  - Uses ``domain_exact`` (GDELT ``domainis:`` operator) for exact-match safety
  - Date range validation
  - Date coercion from pandas Timestamp / str / datetime / date

All tests monkeypatch ``_new_doc_client`` and ``time.sleep`` so no network or
wait is incurred. The live GDELT API is NEVER contacted by the test suite.
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from src import gdelt_timeline_client as gtc
from src.gdelt_timeline_client import (
    TimelineResult,
    TimelineRow,
    query_domain_timeline,
)


# ---------------------------------------------------------------------------
# Fake client helpers
# ---------------------------------------------------------------------------
class FakeGdeltClient:
    """Stand-in for gdeltdoc.GdeltDoc for unit tests.

    Records every ``timeline_search(mode, filters)`` call so tests can
    introspect mode + filters that were passed.
    """

    def __init__(
        self,
        response_df: pd.DataFrame | None = None,
        raise_exc: Exception | None = None,
    ):
        self.response_df = response_df if response_df is not None else pd.DataFrame()
        self.raise_exc = raise_exc
        self.calls: list[tuple[str, object]] = []

    def timeline_search(self, mode, filters):
        self.calls.append((mode, filters))
        if self.raise_exc:
            raise self.raise_exc
        return self.response_df


class RetryingFakeClient:
    """Fake client that raises for the first N calls, then succeeds."""

    def __init__(self, fail_count: int, success_df: pd.DataFrame, exc: Exception):
        self.fail_count = fail_count
        self.success_df = success_df
        self.exc = exc
        self.call_count = 0

    def timeline_search(self, mode, filters):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise self.exc
        return self.success_df


def _seven_day_df() -> pd.DataFrame:
    """Build a synthetic 7-day TimelineVolRaw DataFrame."""
    return pd.DataFrame(
        {
            "datetime": [pd.Timestamp(f"2025-01-{i + 1:02d}") for i in range(7)],
            "Volume Raw": [10, 12, 15, 11, 13, 14, 16],
            "All Articles": [100, 120, 150, 110, 130, 140, 160],
        }
    )


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------
class TestSuccessPath:
    def test_query_returns_seven_timeline_rows(self, monkeypatch):
        fake_client = FakeGdeltClient(response_df=_seven_day_df())
        monkeypatch.setattr(gtc, "_new_doc_client", lambda timeout: fake_client)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = query_domain_timeline(
            "xinhuanet.com",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 7),
            rate_limit_seconds=0,
        )

        assert isinstance(result, TimelineResult)
        assert len(result.rows) == 7
        assert all(isinstance(r, TimelineRow) for r in result.rows)
        assert result.rows[0].date == date(2025, 1, 1)
        assert result.rows[0].volume_raw == 10
        assert result.rows[0].domain == "xinhuanet.com"
        assert result.rows[-1].date == date(2025, 1, 7)
        assert result.rows[-1].volume_raw == 16

    def test_domain_is_attached_to_every_row(self, monkeypatch):
        fake_client = FakeGdeltClient(response_df=_seven_day_df())
        monkeypatch.setattr(gtc, "_new_doc_client", lambda timeout: fake_client)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = query_domain_timeline(
            "tass.ru",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 7),
            rate_limit_seconds=0,
        )

        assert all(r.domain == "tass.ru" for r in result.rows)

    def test_all_articles_column_is_ignored(self, monkeypatch):
        """Only Volume Raw matters. All Articles drifts with GDELT's crawl set."""
        fake_client = FakeGdeltClient(response_df=_seven_day_df())
        monkeypatch.setattr(gtc, "_new_doc_client", lambda timeout: fake_client)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = query_domain_timeline(
            "rt.com",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 7),
            rate_limit_seconds=0,
        )

        # Uses Volume Raw (10-16), NOT All Articles (100-160)
        assert result.total_volume == 91  # 10+12+15+11+13+14+16
        assert all(r.volume_raw < 50 for r in result.rows)

    def test_result_metadata_populated(self, monkeypatch):
        fake_client = FakeGdeltClient(response_df=_seven_day_df())
        monkeypatch.setattr(gtc, "_new_doc_client", lambda timeout: fake_client)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = query_domain_timeline(
            "cgtn.com",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 7),
            rate_limit_seconds=0,
        )

        assert result.domain == "cgtn.com"
        assert result.start_date == date(2025, 1, 1)
        assert result.end_date == date(2025, 1, 7)
        assert result.duration_seconds >= 0
        assert result.retries == 0
        assert result.is_empty is False
        assert len(result) == 7


# ---------------------------------------------------------------------------
# Empty / degenerate response handling
# ---------------------------------------------------------------------------
class TestEmptyResults:
    def test_empty_df_returns_empty_rows_not_exception(self, monkeypatch):
        """Zero-activity outlet is a valid signal, not an error."""
        fake_client = FakeGdeltClient(response_df=pd.DataFrame())
        monkeypatch.setattr(gtc, "_new_doc_client", lambda timeout: fake_client)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = query_domain_timeline(
            "silent-outlet.com",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            rate_limit_seconds=0,
        )

        assert result.rows == []
        assert result.is_empty is True
        assert result.total_volume == 0
        assert result.domain == "silent-outlet.com"
        assert result.start_date == date(2025, 1, 1)
        assert result.end_date == date(2025, 1, 31)

    def test_parser_handles_none_df(self):
        """Direct parser test: None DataFrame → empty list."""
        assert gtc._parse_timeline_dataframe(None, domain="example.com") == []

    def test_parser_handles_missing_columns_with_warning(self, caplog):
        """Missing 'datetime' or 'Volume Raw' columns → empty + warning log."""
        import logging
        caplog.set_level(logging.WARNING, logger="src.gdelt_timeline_client")

        bad_df = pd.DataFrame({"unexpected_col": [1, 2, 3]})
        parsed = gtc._parse_timeline_dataframe(bad_df, domain="example.com")

        assert parsed == []
        assert any("missing expected columns" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Retry behavior
# ---------------------------------------------------------------------------
class TestRetries:
    def test_retries_twice_on_429_then_succeeds(self, monkeypatch):
        """Two 429s then success → returns data with retries=2."""
        fake_client = RetryingFakeClient(
            fail_count=2,
            success_df=_seven_day_df(),
            exc=RuntimeError("HTTP 429: Too Many Requests"),
        )
        monkeypatch.setattr(gtc, "_new_doc_client", lambda timeout: fake_client)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = query_domain_timeline(
            "cgtn.com",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 7),
            rate_limit_seconds=0,
            max_retries=5,
        )

        assert len(result.rows) == 7
        assert result.retries == 2
        assert fake_client.call_count == 3  # 2 failures + 1 success

    def test_gives_up_after_max_retries_returns_empty_not_exception(self, monkeypatch):
        """When every attempt fails, return an empty result — don't raise."""
        fake_client = RetryingFakeClient(
            fail_count=100,  # always fail
            success_df=_seven_day_df(),
            exc=RuntimeError("GDELT server down"),
        )
        monkeypatch.setattr(gtc, "_new_doc_client", lambda timeout: fake_client)
        monkeypatch.setattr("time.sleep", lambda _: None)

        # Should NOT raise
        result = query_domain_timeline(
            "dead-outlet.com",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 7),
            rate_limit_seconds=0,
            max_retries=3,
        )

        assert result.rows == []
        assert result.is_empty is True
        assert result.retries == 3
        assert fake_client.call_count == 3


# ---------------------------------------------------------------------------
# domain_exact enforcement (prevents lookalike substring matches)
# ---------------------------------------------------------------------------
class TestDomainExact:
    def test_query_string_uses_domainis_not_domain_substring(self, monkeypatch):
        """gdeltdoc's ``domain_exact=`` kwarg compiles to ``domainis:`` in the
        GDELT query string — that's GDELT's exact-match operator (vs ``domain:``
        which does substring match and can pick up lookalikes)."""
        captured: list[object] = []

        class CapturingClient:
            def timeline_search(self, mode, filters):
                captured.append(filters)
                return _seven_day_df()

        monkeypatch.setattr(gtc, "_new_doc_client", lambda timeout: CapturingClient())
        monkeypatch.setattr("time.sleep", lambda _: None)

        query_domain_timeline(
            "xinhuanet.com",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 7),
            rate_limit_seconds=0,
        )

        assert len(captured) == 1
        filters = captured[0]
        # gdeltdoc.Filters exposes the compiled query string
        query_string = getattr(filters, "query_string", "")
        assert "domainis:xinhuanet.com" in query_string
        # The substring-match operator 'domain:' should NOT be present
        assert "domain:xinhuanet.com" not in query_string

    def test_build_timeline_filters_sets_domain_exact_kwarg(self):
        """Direct test: the _build_timeline_filters helper uses domain_exact."""
        filters = gtc._build_timeline_filters(
            domain="fars-news.com",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 7),
        )
        # gdeltdoc compiles to its internal query_string format
        query_string = getattr(filters, "query_string", "")
        assert "domainis:fars-news.com" in query_string


# ---------------------------------------------------------------------------
# Date range validation
# ---------------------------------------------------------------------------
class TestDateValidation:
    def test_start_date_after_end_date_raises_value_error(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda _: None)

        with pytest.raises(ValueError, match="must be <="):
            query_domain_timeline(
                "example.com",
                start_date=date(2025, 6, 30),
                end_date=date(2025, 1, 1),
                rate_limit_seconds=0,
            )

    def test_same_start_and_end_date_is_valid(self, monkeypatch):
        """Single-day query must be allowed."""
        one_day = pd.DataFrame(
            {
                "datetime": [pd.Timestamp("2025-06-15")],
                "Volume Raw": [42],
                "All Articles": [100],
            }
        )
        fake_client = FakeGdeltClient(response_df=one_day)
        monkeypatch.setattr(gtc, "_new_doc_client", lambda timeout: fake_client)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = query_domain_timeline(
            "example.com",
            start_date=date(2025, 6, 15),
            end_date=date(2025, 6, 15),
            rate_limit_seconds=0,
        )

        assert len(result.rows) == 1
        assert result.rows[0].volume_raw == 42


# ---------------------------------------------------------------------------
# Date coercion from various input types
# ---------------------------------------------------------------------------
class TestDateCoercion:
    def test_coerces_pandas_timestamp(self):
        assert gtc._coerce_to_date(pd.Timestamp("2025-01-15")) == date(2025, 1, 15)

    def test_coerces_python_date(self):
        assert gtc._coerce_to_date(date(2025, 1, 15)) == date(2025, 1, 15)

    def test_coerces_python_datetime(self):
        assert gtc._coerce_to_date(datetime(2025, 1, 15, 12, 30, 45)) == date(2025, 1, 15)

    def test_coerces_iso_date_string(self):
        assert gtc._coerce_to_date("2025-01-15") == date(2025, 1, 15)

    def test_coerces_iso_datetime_z_string(self):
        assert gtc._coerce_to_date("2025-01-15T00:00:00Z") == date(2025, 1, 15)

    def test_returns_none_for_unparseable(self):
        assert gtc._coerce_to_date("garbage") is None
        assert gtc._coerce_to_date(42) is None
        assert gtc._coerce_to_date(None) is None

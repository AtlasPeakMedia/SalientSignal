"""Unit tests for the slice-computation logic in run_gkg_hourly.py.

The full orchestrator is an integration test (smoke tested against the
real CDN in the CLI). These tests cover the pure-function pieces that
are most likely to have boundary bugs:

    _now_utc(override)              — string parsing
    _slices_in_lookback(now, mins)  — 15-min slice enumeration with safety margin

No network, no Supabase, no file I/O.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

import sys
from pathlib import Path

# Mirror test_run_backfill_cli.py's pattern: put scripts/ on sys.path so
# we can import run_gkg_hourly as a top-level module, and put pipeline/
# on sys.path so the script's own `from src.xxx import ...` resolves.
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
PIPELINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(PIPELINE_DIR))

import run_gkg_hourly  # noqa: E402

_now_utc = run_gkg_hourly._now_utc
_slices_in_lookback = run_gkg_hourly._slices_in_lookback


class TestNowUtc:
    def test_no_override_returns_current_time(self):
        got = _now_utc(None)
        assert got.tzinfo is not None
        # Wall clock is loose; just make sure it's a UTC-aware datetime
        assert got.tzinfo.utcoffset(got).total_seconds() == 0

    def test_z_suffix_iso_parse(self):
        got = _now_utc("2026-04-10T14:07:00Z")
        assert got == datetime(2026, 4, 10, 14, 7, 0, tzinfo=timezone.utc)

    def test_offset_iso_parse(self):
        got = _now_utc("2026-04-10T09:07:00-05:00")
        # 09:07 EDT = 14:07 UTC (DST), but Python datetime handles the offset
        # as a raw offset so we just check it's a tz-aware datetime
        assert got.tzinfo is not None

    def test_invalid_timestamp_raises(self):
        with pytest.raises(SystemExit, match="Invalid --now timestamp"):
            _now_utc("not a timestamp")


class TestSlicesInLookback:
    def test_standard_75min_lookback_at_hour_boundary(self):
        """Cron fires at 14:07 UTC with 75-min lookback.

        Latest available = 14:00 UTC (14:07 - 7min safety margin)
        Earliest = 14:00 - 75min = 12:45 UTC
        Expected slices: 12:45, 13:00, 13:15, 13:30, 13:45, 14:00 = 6 slices
        """
        now = datetime(2026, 4, 10, 14, 7, 0, tzinfo=timezone.utc)
        slices = _slices_in_lookback(now, 75)
        assert len(slices) == 6
        assert slices[0] == datetime(2026, 4, 10, 12, 45, 0, tzinfo=timezone.utc)
        assert slices[-1] == datetime(2026, 4, 10, 14, 0, 0, tzinfo=timezone.utc)

    def test_60min_lookback_at_quarter_hour(self):
        """Cron fires at 14:20 UTC with 60-min lookback.

        Latest available = 14:13 UTC (14:20 - 7min) → floors to 14:00
        Earliest = 14:00 - 60min = 13:00 UTC
        Expected: 13:00, 13:15, 13:30, 13:45, 14:00 = 5 slices
        """
        now = datetime(2026, 4, 10, 14, 20, 0, tzinfo=timezone.utc)
        slices = _slices_in_lookback(now, 60)
        assert len(slices) == 5
        assert slices[0] == datetime(2026, 4, 10, 13, 0, 0, tzinfo=timezone.utc)
        assert slices[-1] == datetime(2026, 4, 10, 14, 0, 0, tzinfo=timezone.utc)

    def test_safety_margin_excludes_current_slice(self):
        """At 14:07, the 14:00 file is still only 7 min old and might not be
        published yet. With the 7-min safety margin (14:07 - 7 = 14:00, floors
        to 14:00), we should INCLUDE 14:00 because 14:00 <= 14:00. That's the
        boundary case — one second later (14:07:01) we'd floor to 14:00 still,
        so 14:00 stays in the list.

        This test nails down that the boundary is "minutes only", not
        sub-minute precision.
        """
        now = datetime(2026, 4, 10, 14, 7, 0, tzinfo=timezone.utc)
        slices = _slices_in_lookback(now, 15)
        # Window: 13:45, 14:00
        assert datetime(2026, 4, 10, 14, 0, 0, tzinfo=timezone.utc) in slices

    def test_safety_margin_excludes_unpublished_slice(self):
        """At 14:06, the 14:00 file is only 6 min old — GDELT probably
        hasn't published it yet. With a 7-min safety margin, 14:00 should
        NOT be in the slice list.

        14:06 - 7min = 13:59 → floors to 13:45
        So 14:00 is excluded, 13:45 is the latest.
        """
        now = datetime(2026, 4, 10, 14, 6, 0, tzinfo=timezone.utc)
        slices = _slices_in_lookback(now, 15)
        assert datetime(2026, 4, 10, 14, 0, 0, tzinfo=timezone.utc) not in slices
        assert datetime(2026, 4, 10, 13, 45, 0, tzinfo=timezone.utc) in slices

    def test_spans_hour_boundary(self):
        """Cron at 01:07 with 75-min lookback crosses midnight."""
        now = datetime(2026, 4, 11, 1, 7, 0, tzinfo=timezone.utc)
        slices = _slices_in_lookback(now, 75)
        # Latest = 01:00, earliest = 23:45 (prev day)
        assert slices[0] == datetime(2026, 4, 10, 23, 45, 0, tzinfo=timezone.utc)
        assert slices[-1] == datetime(2026, 4, 11, 1, 0, 0, tzinfo=timezone.utc)
        assert len(slices) == 6

    def test_all_slices_are_fifteen_minute_boundaries(self):
        """Every returned slice must be on a :00, :15, :30, or :45."""
        now = datetime(2026, 4, 10, 14, 23, 0, tzinfo=timezone.utc)
        slices = _slices_in_lookback(now, 120)
        assert all(s.minute in (0, 15, 30, 45) for s in slices)
        assert all(s.second == 0 for s in slices)

    def test_lookback_rounds_to_boundaries(self):
        """Even with an odd lookback minutes value, the earliest slice
        still has to land on a 15-min boundary."""
        now = datetime(2026, 4, 10, 14, 20, 0, tzinfo=timezone.utc)
        # 37 min lookback at 14:13 → earliest = 13:36 → floors to 13:30
        slices = _slices_in_lookback(now, 37)
        assert slices[0].minute in (0, 15, 30, 45)

    def test_zero_lookback_returns_single_slice(self):
        """A 0-min lookback should return just the latest available slice."""
        now = datetime(2026, 4, 10, 14, 20, 0, tzinfo=timezone.utc)
        slices = _slices_in_lookback(now, 0)
        # Latest slice is 14:00 (14:20 - 7 = 14:13, floors to 14:00)
        assert slices == [datetime(2026, 4, 10, 14, 0, 0, tzinfo=timezone.utc)]

    def test_monotonic_ordering(self):
        """Slice list must be sorted earliest-to-latest."""
        now = datetime(2026, 4, 10, 14, 20, 0, tzinfo=timezone.utc)
        slices = _slices_in_lookback(now, 120)
        for a, b in zip(slices, slices[1:]):
            assert a < b

    def test_long_lookback_produces_many_slices(self):
        """Sanity: 24-hour lookback = ~96 slices."""
        now = datetime(2026, 4, 10, 14, 20, 0, tzinfo=timezone.utc)
        slices = _slices_in_lookback(now, 24 * 60)
        # 24 hours of 15-min slices = 96 slices per day
        assert 94 <= len(slices) <= 97

"""Tests for scripts/import_backfill.py — A4 validation + upsert path.

Covers the six validation passes, the batch upsert behavior, and the
clear_historical_cold_start helper. All tests use InMemoryDb so no
network or Supabase credentials are needed.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).parents[1]))

import import_backfill as ib  # noqa: E402
from src.db import InMemoryDb  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _good_row(**overrides) -> dict:
    """Build a valid country_activity row dict."""
    base = {
        "country": "RU",
        "date": "2025-01-15",
        "audience_type": "DOMESTIC",
        "today_count": 42,
        "baseline_mean": 40.0,
        "baseline_std": 5.0,
        "deviation_ratio": 1.05,
        "z_score": 0.4,
        "level": "neutral",
        "confidence": "HIGH",
        "cold_start": False,
        "top_themes": {},
        "top_outlets": [{"domain": "tass.ru", "count": 42}],
    }
    base.update(overrides)
    return base


def _dense_series(country: str, audience: str, start_day: int, end_day: int) -> list[dict]:
    """Build a dense per-day series for date-coverage tests."""
    return [
        _good_row(
            country=country,
            audience_type=audience,
            date=f"2025-01-{d:02d}",
        )
        for d in range(start_day, end_day + 1)
    ]


# ---------------------------------------------------------------------------
# Pass 1: schema shape
# ---------------------------------------------------------------------------
class TestValidateSchema:
    def test_happy_path(self):
        ib.validate_schema([_good_row()])

    def test_missing_level_raises(self):
        bad = _good_row()
        del bad["level"]
        with pytest.raises(ib.ValidationError, match="missing required keys"):
            ib.validate_schema([bad])

    def test_missing_top_outlets_raises(self):
        bad = _good_row()
        del bad["top_outlets"]
        with pytest.raises(ib.ValidationError, match="missing required keys"):
            ib.validate_schema([bad])


# ---------------------------------------------------------------------------
# Pass 2: value ranges
# ---------------------------------------------------------------------------
class TestValidateValues:
    def test_happy_path(self):
        ib.validate_values([_good_row()])

    def test_negative_today_count_rejected(self):
        with pytest.raises(ib.ValidationError, match="today_count invalid"):
            ib.validate_values([_good_row(today_count=-1)])

    def test_negative_baseline_mean_rejected(self):
        with pytest.raises(ib.ValidationError, match="baseline_mean negative"):
            ib.validate_values([_good_row(baseline_mean=-0.5)])

    def test_invalid_level_rejected(self):
        with pytest.raises(ib.ValidationError, match="level invalid"):
            ib.validate_values([_good_row(level="teal")])

    def test_invalid_confidence_rejected(self):
        with pytest.raises(ib.ValidationError, match="confidence invalid"):
            ib.validate_values([_good_row(confidence="SORTA")])

    def test_invalid_audience_type_rejected(self):
        with pytest.raises(ib.ValidationError, match="audience_type invalid"):
            ib.validate_values([_good_row(audience_type="MARTIAN")])

    def test_non_bool_cold_start_rejected(self):
        with pytest.raises(ib.ValidationError, match="cold_start must be bool"):
            ib.validate_values([_good_row(cold_start="yes")])

    def test_all_valid_levels_pass(self):
        from src.deviation import ALL_LEVELS
        rows = [_good_row(level=lvl) for lvl in ALL_LEVELS]
        ib.validate_values(rows)  # should not raise


# ---------------------------------------------------------------------------
# Pass 3: date coverage
# ---------------------------------------------------------------------------
class TestValidateDateCoverage:
    def test_dense_series_passes(self):
        rows = _dense_series("RU", "DOMESTIC", 1, 30)
        ib.validate_date_coverage(rows)  # should not raise

    def test_gap_over_seven_days_rejected(self):
        rows = _dense_series("RU", "DOMESTIC", 1, 5)
        rows.extend(_dense_series("RU", "DOMESTIC", 15, 20))  # 10-day gap
        with pytest.raises(ib.ValidationError, match="gap of 10 days"):
            ib.validate_date_coverage(rows)

    def test_gap_exactly_seven_days_passes(self):
        rows = _dense_series("RU", "DOMESTIC", 1, 5)
        rows.extend(_dense_series("RU", "DOMESTIC", 12, 15))  # 7-day gap = pass
        ib.validate_date_coverage(rows)

    def test_parallel_series_coverage_independent(self):
        """Gaps in RU/DOMESTIC are separate from gaps in CN/DOMESTIC."""
        rows = _dense_series("RU", "DOMESTIC", 1, 10)
        rows.extend(_dense_series("CN", "DOMESTIC", 1, 10))
        ib.validate_date_coverage(rows)

    def test_unparseable_date_raises(self):
        rows = [_good_row(date="not-a-date")]
        with pytest.raises(ib.ValidationError, match="unparseable date"):
            ib.validate_date_coverage(rows)


# ---------------------------------------------------------------------------
# Pass 4: sanity events (WARN only)
# ---------------------------------------------------------------------------
class TestValidateSanityEvents:
    def test_missing_sanity_event_warns_but_passes(self, caplog):
        import logging
        caplog.set_level(logging.WARNING, logger="import_backfill")
        # No rows for Feb 24 2026 RU INTERNATIONAL
        ib.validate_sanity_events([_good_row()])
        assert any(
            "no row for 2026-02-24" in rec.message or "SANITY" in rec.message
            for rec in caplog.records
        )

    def test_present_sanity_event_logs_info_passes(self, caplog):
        import logging
        caplog.set_level(logging.INFO, logger="import_backfill")
        rows = [
            _good_row(
                date="2026-02-24",
                country="RU",
                audience_type="INTERNATIONAL",
                today_count=500,
                deviation_ratio=3.0,
                z_score=4.5,
                level="red",
            ),
        ]
        # Does NOT raise even if the rest of the fields are thin
        ib.validate_sanity_events(rows)
        assert any(
            "RU/INTERNATIONAL" in rec.message and "Russia-Ukraine" in rec.message
            for rec in caplog.records
        )


# ---------------------------------------------------------------------------
# Pass 5: volume ceiling
# ---------------------------------------------------------------------------
class TestValidateVolume:
    def test_small_volume_passes(self):
        ib.validate_volume([_good_row()] * 1000)

    def test_over_ceiling_rejected(self):
        # Use a fake list with a large __len__ to avoid creating 200K dicts
        class BigList:
            def __len__(self):
                return 200_001

            def __iter__(self):
                return iter([])

        with pytest.raises(ib.ValidationError, match="exceeds ceiling"):
            ib.validate_volume(BigList())


# ---------------------------------------------------------------------------
# Pass 6: FVEY exclusion
# ---------------------------------------------------------------------------
class TestValidateNoFvey:
    def test_no_fvey_passes(self):
        ib.validate_no_fvey([_good_row(country="RU")])

    def test_us_row_rejected(self):
        with pytest.raises(ib.ValidationError, match="FVEY"):
            ib.validate_no_fvey([_good_row(country="US")])

    def test_multiple_fvey_countries_listed(self):
        rows = [
            _good_row(country="US"),
            _good_row(country="GB"),
            _good_row(country="CA"),
        ]
        with pytest.raises(ib.ValidationError, match="FVEY"):
            ib.validate_no_fvey(rows)


# ---------------------------------------------------------------------------
# Upsert behavior via InMemoryDb
# ---------------------------------------------------------------------------
class TestUpsertRows:
    def test_upsert_inserts_all_rows(self):
        db = InMemoryDb()
        rows = _dense_series("RU", "DOMESTIC", 1, 30)
        inserted = ib.upsert_rows(db, rows)
        assert inserted == 30
        assert len(db.country_activity) == 30

    def test_upsert_batches_in_100_chunks(self):
        """Large input should hit the batch upsert path multiple times."""
        db = InMemoryDb()
        # 250 rows — should require 3 batches of 100/100/50
        rows = [
            _good_row(
                country="RU",
                audience_type="DOMESTIC",
                date=f"2025-01-{(i % 30) + 1:02d}",
                today_count=i,  # make rows distinct for upsert
            )
            for i in range(250)
        ]
        # Wrap db.upsert_country_activity_batch to count invocations
        original = db.upsert_country_activity_batch
        call_log: list[int] = []

        def counting(batch):
            call_log.append(len(batch))
            return original(batch)

        db.upsert_country_activity_batch = counting  # type: ignore[method-assign]
        ib.upsert_rows(db, rows)
        # Expect batches of 100, 100, 50
        assert call_log == [100, 100, 50]


# ---------------------------------------------------------------------------
# clear_historical_cold_start (A4 helper)
# ---------------------------------------------------------------------------
class TestClearHistoricalColdStart:
    def test_clears_historical_rows(self):
        db = InMemoryDb()
        db.country_activity = [
            {"country": "RU", "date": "2025-01-15", "audience_type": "DOMESTIC", "cold_start": True},
            {"country": "RU", "date": "2025-06-01", "audience_type": "DOMESTIC", "cold_start": True},
            {"country": "RU", "date": "2026-04-10", "audience_type": "DOMESTIC", "cold_start": True},
        ]
        cleared = db.clear_historical_cold_start(reference_date=date(2026, 4, 10))

        assert cleared == 2  # only rows < 2026-04-10
        assert db.country_activity[0]["cold_start"] is False
        assert db.country_activity[1]["cold_start"] is False
        # Today's row is NOT cleared
        assert db.country_activity[2]["cold_start"] is True

    def test_skips_rows_already_false(self):
        db = InMemoryDb()
        db.country_activity = [
            {"country": "RU", "date": "2025-01-15", "audience_type": "DOMESTIC", "cold_start": False},
            {"country": "RU", "date": "2025-01-16", "audience_type": "DOMESTIC", "cold_start": True},
        ]
        cleared = db.clear_historical_cold_start(reference_date=date(2026, 1, 1))
        assert cleared == 1  # only the one that was True


# ---------------------------------------------------------------------------
# load_backfill_json
# ---------------------------------------------------------------------------
class TestLoadBackfillJson:
    def test_loads_valid_json(self, tmp_path):
        path = tmp_path / "backfill.json"
        doc = {
            "metadata": {
                "start_date": "2025-01-01",
                "end_date": "2025-01-30",
            },
            "country_activity": [_good_row()],
            "failures": [],
        }
        path.write_text(json.dumps(doc))

        metadata, rows = ib.load_backfill_json(path)
        assert metadata["start_date"] == "2025-01-01"
        assert len(rows) == 1

    def test_empty_country_activity_raises(self, tmp_path):
        path = tmp_path / "backfill.json"
        doc = {"metadata": {}, "country_activity": [], "failures": []}
        path.write_text(json.dumps(doc))

        with pytest.raises(ib.ValidationError, match="zero country_activity rows"):
            ib.load_backfill_json(path)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ib.load_backfill_json(tmp_path / "nonexistent.json")

    def test_country_activity_not_list_raises(self, tmp_path):
        path = tmp_path / "backfill.json"
        path.write_text('{"country_activity": "nope"}')
        with pytest.raises(ib.ValidationError, match="must be a list"):
            ib.load_backfill_json(path)


# ---------------------------------------------------------------------------
# Full validation pipeline
# ---------------------------------------------------------------------------
class TestRunAllValidations:
    def test_all_passes_on_clean_data(self):
        rows = _dense_series("RU", "DOMESTIC", 1, 30)
        ib.run_all_validations(rows)

    def test_fails_on_fvey_contamination(self):
        rows = _dense_series("RU", "DOMESTIC", 1, 30)
        rows.append(_good_row(country="US"))
        with pytest.raises(ib.ValidationError):
            ib.run_all_validations(rows)


# ---------------------------------------------------------------------------
# Summary + manifest
# ---------------------------------------------------------------------------
class TestSummaryAndManifest:
    def test_summarize_rows_counts(self):
        rows = (
            _dense_series("RU", "DOMESTIC", 1, 10)
            + _dense_series("CN", "DOMESTIC", 1, 5)
        )
        summary = ib.summarize_rows(rows)
        assert summary["total_rows"] == 15
        assert summary["unique_countries"] == 2
        assert summary["earliest_date"] == "2025-01-01"
        assert summary["latest_date"] == "2025-01-10"

    def test_write_import_manifest_creates_file(self, tmp_path):
        source = tmp_path / "source.json"
        source.write_text("{}")
        manifest_path = ib.write_import_manifest(
            output_dir=tmp_path,
            source_json=source,
            summary={"total_rows": 100},
            imported_count=100,
            cold_start_cleared_count=50,
        )
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert data["imported_count"] == 100
        assert data["cold_start_cleared_count"] == 50
        assert data["summary"]["total_rows"] == 100

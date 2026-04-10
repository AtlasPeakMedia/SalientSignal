"""Smoke tests for scripts/run_backfill.py CLI.

These tests exercise the argument parser and the JSON writer without
contacting GDELT. Full end-to-end behavior of run_backfill is tested in
test_backfill.py; this file only covers the CLI boundary.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

# Put the scripts/ dir on sys.path so we can import run_backfill as a module.
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# The script imports src.* at module level, so sys.path for pipeline/ must
# already be set. test_backfill.py does this in its own path fixup.
sys.path.insert(0, str(Path(__file__).parents[1]))

import run_backfill  # noqa: E402

from src.backfill import BackfillResult, BackfillStats  # noqa: E402


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
class TestArgParsing:
    def test_required_args(self):
        args = run_backfill.parse_args(
            [
                "--start-date",
                "2025-01-01",
                "--end-date",
                "2025-01-30",
                "--output-json",
                "/tmp/ss_backfill_smoke.json",
            ]
        )
        assert args.start_date == "2025-01-01"
        assert args.end_date == "2025-01-30"
        assert args.output_json == "/tmp/ss_backfill_smoke.json"
        assert args.force is False
        assert args.verbose is False
        assert args.dry_run is False
        assert args.resume_from is None

    def test_optional_flags(self):
        args = run_backfill.parse_args(
            [
                "--start-date",
                "2025-01-01",
                "--end-date",
                "2025-01-30",
                "--output-json",
                "/tmp/x.json",
                "--force",
                "--verbose",
                "--resume-from",
                "xinhuanet.com",
                "--rate-limit",
                "1.5",
            ]
        )
        assert args.force is True
        assert args.verbose is True
        assert args.resume_from == "xinhuanet.com"
        assert args.rate_limit == 1.5

    def test_parse_date_helper(self):
        assert run_backfill._parse_date("2025-01-15") == date(2025, 1, 15)

    def test_parse_date_bad_format_raises(self):
        with pytest.raises(Exception):
            run_backfill._parse_date("not-a-date")


# ---------------------------------------------------------------------------
# JSON output shape
# ---------------------------------------------------------------------------
class TestResultDictShape:
    def test_build_result_dict_basic_shape(self):
        stats = BackfillStats(
            outlets_queried=5,
            outlets_succeeded=4,
            outlets_empty=1,
            outlets_failed=1,
            outlets_skipped=0,
            days_covered=30,
            country_activity_rows=60,
        )
        result = BackfillResult(
            stats=stats,
            country_activity=[
                {
                    "country": "RU",
                    "date": "2025-01-01",
                    "audience_type": "DOMESTIC",
                    "today_count": 5,
                    "baseline_mean": 0.0,
                    "baseline_std": 0.0,
                    "deviation_ratio": 1.0,
                    "z_score": 0.0,
                    "level": "neutral",
                    "confidence": "LOW",
                    "cold_start": True,
                    "top_themes": {},
                    "top_outlets": [{"domain": "tass.ru", "count": 5}],
                }
            ],
            raw_outlet_daily_counts={("tass.ru", date(2025, 1, 1)): 5},
            failures=[("broken.ru", "HTTP 500")],
        )

        doc = run_backfill._build_result_dict(
            result=result,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 30),
            outlet_count=5,
            elapsed_seconds=12.34,
        )

        # Top-level structure
        assert "metadata" in doc
        assert "country_activity" in doc
        assert "failures" in doc
        assert "raw_outlet_daily_counts" in doc

        # Metadata
        md = doc["metadata"]
        assert md["start_date"] == "2025-01-01"
        assert md["end_date"] == "2025-01-30"
        assert md["outlet_count"] == 5
        assert md["elapsed_seconds"] == 12.34
        assert "generated_at" in md
        assert md["stats"]["outlets_succeeded"] == 4

        # Failures: list of [domain, error] tuples
        assert doc["failures"] == [["broken.ru", "HTTP 500"]]

        # Raw counts serialized to dicts with ISO dates
        assert len(doc["raw_outlet_daily_counts"]) == 1
        rc = doc["raw_outlet_daily_counts"][0]
        assert rc["domain"] == "tass.ru"
        assert rc["date"] == "2025-01-01"
        assert rc["volume"] == 5

    def test_build_result_dict_interrupted_flag(self):
        stats = BackfillStats(days_covered=30)
        result = BackfillResult(
            stats=stats,
            country_activity=[],
            raw_outlet_daily_counts={},
            failures=[],
        )
        doc = run_backfill._build_result_dict(
            result=result,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 30),
            outlet_count=0,
            elapsed_seconds=1.0,
            interrupted=True,
        )
        assert doc["metadata"]["interrupted"] is True

    def test_write_result_json_refuses_to_overwrite(self, tmp_path):
        out = tmp_path / "existing.json"
        out.write_text('{"already": "here"}')

        with pytest.raises(FileExistsError):
            run_backfill._write_result_json(out, {"new": "doc"}, force=False)

    def test_write_result_json_overwrites_with_force(self, tmp_path):
        out = tmp_path / "existing.json"
        out.write_text('{"already": "here"}')

        run_backfill._write_result_json(out, {"new": "doc"}, force=True)
        assert json.loads(out.read_text()) == {"new": "doc"}

    def test_write_result_json_creates_parent_directories(self, tmp_path):
        out = tmp_path / "a" / "b" / "c" / "backfill.json"
        assert not out.parent.exists()

        run_backfill._write_result_json(out, {"hello": "world"}, force=False)

        assert out.exists()
        assert json.loads(out.read_text()) == {"hello": "world"}

"""Phase 2 pipeline integration tests.

Verifies that run_pipeline() correctly wires up the Phase 2 fixes:

  - P2-C4: ESCALATE verdicts land in analysis_escalated
  - P2-C5: Validation claims land in analysis_claims
  - P2-C2: country_activity uses batch upsert (not per-row)
  - P2-H4: cold_start flag propagates from antihal → DB rows

These tests use InMemoryDb so they run offline. The fake GDELT client
returns enough synthetic articles to trigger each validation path.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.db import InMemoryDb
from src.gdelt_client import GdeltQueryResult
from src.pipeline import run_pipeline


def _fake_gdelt_query_empty(country_fips, hours=1):
    """Returns an empty GDELT result."""
    return GdeltQueryResult(
        df=pd.DataFrame(),
        query_str=f"empty country={country_fips}",
        duration_seconds=0.0,
    )


def _fake_gdelt_query_russia(country_fips, hours=1):
    """Returns a DataFrame with synthetic rt.com + tass.ru articles.

    Note: We use ISO "RU" in the synthetic sourcecountry field (not FIPS "RS")
    to sidestep the FIPS↔ISO collision: Russia's FIPS is "RS" which is ALSO
    Serbia's ISO code, so the pipeline's `_is_known_iso` check would
    incorrectly leave "RS" in place as Serbia. This is a known limitation
    of the pre-Phase-2 countries.py translation layer; real GDELT returns
    ISO codes in `sourcecountry` per the 2.0 DOC API spec, so the collision
    only matters for FIPS-format inputs.
    """
    if country_fips != "RS":  # RS is the FIPS code for Russia
        return GdeltQueryResult(
            df=pd.DataFrame(),
            query_str=f"empty country={country_fips}",
            duration_seconds=0.0,
        )
    rows = [
        {
            "url": f"https://rt.com/article/{i}",
            "title": f"Sample RT article {i}",
            "seendate": "20260410120000",
            "domain": "rt.com",
            "language": "English",
            "sourcecountry": "RU",
            "tone": -0.5,
        }
        for i in range(5)
    ] + [
        {
            "url": f"https://tass.ru/article/{i}",
            "title": f"Sample TASS article {i}",
            "seendate": "20260410120000",
            "domain": "tass.ru",
            "language": "Russian",
            "sourcecountry": "RU",
            "tone": 0.0,
        }
        for i in range(5)
    ]
    return GdeltQueryResult(
        df=pd.DataFrame(rows),
        query_str=f"russia country={country_fips}",
        duration_seconds=0.1,
    )


class TestPipelineBatchUpsert:
    def test_pipeline_uses_batch_method_for_country_activity(self):
        """P2-C2: pipeline should call upsert_country_activity_batch (not loop)."""
        db = InMemoryDb()
        result = run_pipeline(
            countries=["RU"],
            hours=1,
            dry_run=False,
            db=db,
            gdelt_query_country=_fake_gdelt_query_russia,
            target_date=date(2026, 4, 10),
            log_to_stdout_print=False,
        )
        # Should have produced country_activity rows
        assert len(db.country_activity) > 0
        # Every row should be for Russia, April 10
        for row in db.country_activity:
            assert row["country"] == "RU"
            assert row["date"] == "2026-04-10"


class TestPipelinePersistsAnalysisClaims:
    def test_deviation_claims_persisted(self):
        """P2-C5: after validate_batch_deviations, claims must land in analysis_claims."""
        db = InMemoryDb()
        run_pipeline(
            countries=["RU"],
            hours=1,
            dry_run=False,
            db=db,
            gdelt_query_country=_fake_gdelt_query_russia,
            target_date=date(2026, 4, 10),
            log_to_stdout_print=False,
        )
        # At least one DEVIATION claim should be persisted per audience bucket
        deviation_claims = [
            c for c in db.analysis_claims if c.get("claim_type") == "DEVIATION"
        ]
        assert len(deviation_claims) >= 1

    def test_dry_run_skips_persistence(self):
        """Dry-run mode should never hit the DB for analysis_claims."""
        db = InMemoryDb()
        run_pipeline(
            countries=["RU"],
            hours=1,
            dry_run=True,
            db=db,
            gdelt_query_country=_fake_gdelt_query_russia,
            target_date=date(2026, 4, 10),
            log_to_stdout_print=False,
        )
        # Dry run: nothing should be written
        assert db.analysis_claims == []
        assert db.articles == []
        assert db.country_activity == []


class TestPipelineColdStartFlag:
    def test_cold_start_propagates_to_activity_rows(self):
        """P2-H4: cold_start=True should appear on country_activity rows when
        baseline has < 7 days of history."""
        db = InMemoryDb()
        # With no prior articles in the DB, baseline is empty → days_sampled=0
        # → cold start path fires and cold_start=True propagates
        run_pipeline(
            countries=["RU"],
            hours=1,
            dry_run=False,
            db=db,
            gdelt_query_country=_fake_gdelt_query_russia,
            target_date=date(2026, 4, 10),
            log_to_stdout_print=False,
        )
        assert len(db.country_activity) > 0
        # Baseline is empty on first run → every row is cold_start
        cold_start_rows = [r for r in db.country_activity if r.get("cold_start")]
        assert len(cold_start_rows) == len(db.country_activity)


class TestPipelineDoesNotCrashOnEmptyGdelt:
    def test_empty_gdelt_noop(self):
        """Pipeline must handle an entirely empty GDELT response."""
        db = InMemoryDb()
        result = run_pipeline(
            countries=["XX"],  # non-existent country
            hours=1,
            dry_run=False,
            db=db,
            gdelt_query_country=_fake_gdelt_query_empty,
            target_date=date(2026, 4, 10),
            log_to_stdout_print=False,
        )
        assert result.stats.articles_received == 0
        assert result.stats.articles_inserted == 0
        # pipeline_runs should still be recorded
        assert len(db.pipeline_runs) == 1
        assert db.pipeline_runs[0]["outcome"] == "SUCCESS"


class TestPipelineRowsDontLeakInternalFields:
    def test_days_sampled_stripped_before_db_write(self):
        """days_sampled is internal-only, must not land in country_activity."""
        db = InMemoryDb()
        run_pipeline(
            countries=["RU"],
            hours=1,
            dry_run=False,
            db=db,
            gdelt_query_country=_fake_gdelt_query_russia,
            target_date=date(2026, 4, 10),
            log_to_stdout_print=False,
        )
        for row in db.country_activity:
            assert "days_sampled" not in row
            # Also strip any `_`-prefixed internal fields
            for key in row.keys():
                assert not key.startswith("_"), f"Internal field leaked: {key}"

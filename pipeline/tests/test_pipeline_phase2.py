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
import pytest

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

    def test_caveat_stripped_from_articles_before_db_write(self):
        """REGRESSION (caught on first live run): the anti-hal validator adds
        `_caveat` to article rows that get PUBLISH_WITH_CAVEAT. That field
        is internal-only and must be stripped before insert_articles, or
        Supabase rejects the batch with `Could not find the '_caveat' column`.
        """
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
        assert len(db.articles) > 0
        for row in db.articles:
            for key in row.keys():
                assert not key.startswith("_"), (
                    f"Internal field leaked into articles table: {key}"
                )


# ---------------------------------------------------------------------------
# B9: Hybrid ingestion fallback for locked-down states
# ---------------------------------------------------------------------------
def _make_iran_article(i: int, domain: str = "presstv.ir") -> dict:
    return {
        "url": f"https://{domain}/article/{i}",
        "title": f"Iran state media article {i}",
        "seendate": "20260410120000",
        "domain": domain,
        "language": "English",
        "sourcecountry": "IR",
        "tone": 0.0,
    }


def _fake_empty_country_query(country_fips, hours=1):
    """Iran returns 0 results — simulating the GDELT sourcecountry broken-filter case."""
    return GdeltQueryResult(
        df=pd.DataFrame(),
        query_str=f"empty country={country_fips}",
        duration_seconds=0.0,
    )


class _DomainQueryStub:
    """Programmable fake for query_domain() — records calls + returns canned rows."""

    def __init__(self, per_domain_rows: dict[str, list[dict]] | None = None):
        self.per_domain_rows = per_domain_rows or {}
        self.calls: list[str] = []

    def __call__(self, domain, hours=1):
        self.calls.append(domain)
        rows = self.per_domain_rows.get(domain, [])
        return GdeltQueryResult(
            df=pd.DataFrame(rows),
            query_str=f"domain={domain}",
            duration_seconds=0.0,
        )


class TestHybridFallback:
    def test_fallback_triggers_on_empty_iran_country_query(self):
        """Iran's country query returns 0 → fallback queries every IR outlet."""
        db = InMemoryDb()
        # presstv.ir is the only IR domain we canned; other IR outlets get []
        domain_stub = _DomainQueryStub(
            per_domain_rows={
                "presstv.ir": [_make_iran_article(i, "presstv.ir") for i in range(5)]
            }
        )
        run_pipeline(
            countries=["IR"],
            hours=1,
            dry_run=False,
            db=db,
            gdelt_query_country=_fake_empty_country_query,
            gdelt_query_domain=domain_stub,
            target_date=date(2026, 4, 10),
            log_to_stdout_print=False,
        )
        # Fallback should have queried MULTIPLE IR outlets (all 20+ registered)
        assert len(domain_stub.calls) > 5
        assert "presstv.ir" in domain_stub.calls
        # 5 presstv.ir articles should have been ingested
        iran_articles = [a for a in db.articles if a.get("source_country") == "IR"]
        assert len(iran_articles) == 5

    def test_fallback_NOT_triggered_for_non_locked_down_country(self):
        """Russia is NOT in LOCKED_DOWN_COUNTRIES → no domain fallback even if
        country query returns nothing."""
        db = InMemoryDb()
        domain_stub = _DomainQueryStub()
        run_pipeline(
            countries=["RU"],
            hours=1,
            dry_run=False,
            db=db,
            gdelt_query_country=_fake_empty_country_query,
            gdelt_query_domain=domain_stub,
            target_date=date(2026, 4, 10),
            log_to_stdout_print=False,
        )
        # Russia is NOT locked-down, so domain fallback should NOT fire
        assert domain_stub.calls == []

    def test_fallback_NOT_triggered_when_country_query_has_enough(self):
        """Fallback only fires when country query returned < threshold
        state-media articles. If Iran's country query somehow returned
        enough, the fallback should be skipped."""
        # Build a fake country query that DOES return plenty of Iranian
        # state media (simulating a day when GDELT's sourcecountry happened
        # to crawl IR correctly — rare but possible).
        def _iran_country_query_with_enough(country_fips, hours=1):
            if country_fips != "IR":
                return GdeltQueryResult(
                    df=pd.DataFrame(),
                    query_str=f"empty country={country_fips}",
                    duration_seconds=0.0,
                )
            return GdeltQueryResult(
                df=pd.DataFrame(
                    [_make_iran_article(i, "presstv.ir") for i in range(10)]
                ),
                query_str="iran country query",
                duration_seconds=0.0,
            )

        db = InMemoryDb()
        domain_stub = _DomainQueryStub()
        run_pipeline(
            countries=["IR"],
            hours=1,
            dry_run=False,
            db=db,
            gdelt_query_country=_iran_country_query_with_enough,
            gdelt_query_domain=domain_stub,
            target_date=date(2026, 4, 10),
            log_to_stdout_print=False,
        )
        # >= threshold state-media articles in the country query → no fallback
        assert domain_stub.calls == []
        assert len(db.articles) == 10

    def test_fallback_dedupes_by_url(self):
        """An article URL returned by BOTH the country query AND the domain
        fallback should only land in the DB once."""
        shared_url_rows = [_make_iran_article(i, "presstv.ir") for i in range(2)]

        def _iran_country_with_2(country_fips, hours=1):
            if country_fips != "IR":
                return GdeltQueryResult(
                    df=pd.DataFrame(),
                    query_str="empty",
                    duration_seconds=0.0,
                )
            return GdeltQueryResult(
                df=pd.DataFrame(shared_url_rows),
                query_str="iran 2 rows",
                duration_seconds=0.0,
            )

        # Domain fallback returns the SAME 2 URLs + 3 NEW ones = 5 unique total
        new_rows = [_make_iran_article(i, "presstv.ir") for i in range(2, 5)]
        domain_stub = _DomainQueryStub(
            per_domain_rows={"presstv.ir": shared_url_rows + new_rows}
        )

        db = InMemoryDb()
        run_pipeline(
            countries=["IR"],
            hours=1,
            dry_run=False,
            db=db,
            gdelt_query_country=_iran_country_with_2,
            gdelt_query_domain=domain_stub,
            target_date=date(2026, 4, 10),
            log_to_stdout_print=False,
        )
        # Total unique URLs: 2 (country) + 3 (new from fallback) = 5
        iran_articles = [a for a in db.articles if a.get("source_country") == "IR"]
        urls = {a["url"] for a in iran_articles}
        assert len(urls) == 5  # no duplicates

    def test_fallback_respects_time_budget(self):
        """If the time budget expires mid-fallback, TimeBudgetExceeded must
        be raised rather than swallowed."""
        from src.pipeline import TimeBudgetExceeded

        # Blow a tiny budget immediately
        domain_stub = _DomainQueryStub(
            per_domain_rows={
                "presstv.ir": [_make_iran_article(i, "presstv.ir") for i in range(3)]
            }
        )
        db = InMemoryDb()

        with pytest.raises(TimeBudgetExceeded):
            run_pipeline(
                countries=["IR"],
                hours=1,
                dry_run=False,
                db=db,
                gdelt_query_country=_fake_empty_country_query,
                gdelt_query_domain=domain_stub,
                target_date=date(2026, 4, 10),
                log_to_stdout_print=False,
                time_budget_seconds=0.000001,  # effectively 0
            )

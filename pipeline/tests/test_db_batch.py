"""Phase 2 DB batch method tests.

Tests the InMemoryDb implementations of:

  - P2-C1: insert_articles batching
  - P2-C2: upsert_country_activity_batch
  - P2-C4: insert_analysis_escalated
  - P2-C5: insert_analysis_claims
  - P2-C9: get_schema_version
  - verify_write_permission no-op

These tests use InMemoryDb so they run without a real Supabase instance.
They verify the INTERFACE contract — the real Supabase client matches the
same signature, so any wiring errors would show up here first.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.db import REQUIRED_SCHEMA_VERSION, InMemoryDb


class TestInsertArticlesBatch:
    def test_empty_list_returns_zero(self):
        db = InMemoryDb()
        assert db.insert_articles([]) == 0
        assert db.articles == []

    def test_single_batch(self):
        db = InMemoryDb()
        rows = [
            {"url": f"https://rt.com/{i}", "source_country": "RU",
             "audience_type": "INTERNATIONAL"}
            for i in range(10)
        ]
        inserted = db.insert_articles(rows)
        assert inserted == 10
        assert len(db.articles) == 10

    def test_large_insert(self):
        db = InMemoryDb()
        rows = [
            {"url": f"https://rt.com/{i}", "source_country": "RU",
             "audience_type": "INTERNATIONAL"}
            for i in range(5000)
        ]
        inserted = db.insert_articles(rows)
        assert inserted == 5000
        assert len(db.articles) == 5000


class TestUpsertCountryActivityBatch:
    def test_batch_method_exists_and_works(self):
        """P2-C2: batch method must accept a list of rows."""
        db = InMemoryDb()
        rows = [
            {"country": "RU", "date": "2026-04-10",
             "audience_type": "INTERNATIONAL", "today_count": 100},
            {"country": "CN", "date": "2026-04-10",
             "audience_type": "DOMESTIC", "today_count": 200},
            {"country": "IR", "date": "2026-04-10",
             "audience_type": "INTERNATIONAL", "today_count": 50},
        ]
        inserted = db.upsert_country_activity_batch(rows)
        assert inserted == 3
        assert len(db.country_activity) == 3

    def test_single_row_compatibility_shim(self):
        """upsert_country_activity (single) should still work for backward compat."""
        db = InMemoryDb()
        db.upsert_country_activity({
            "country": "RU", "date": "2026-04-10",
            "audience_type": "INTERNATIONAL", "today_count": 100,
        })
        assert len(db.country_activity) == 1

    def test_upsert_replaces_existing_row(self):
        """Upsert semantics: re-insert same (country, date, audience) replaces."""
        db = InMemoryDb()
        rows_v1 = [{"country": "RU", "date": "2026-04-10",
                    "audience_type": "INTERNATIONAL", "today_count": 100}]
        rows_v2 = [{"country": "RU", "date": "2026-04-10",
                    "audience_type": "INTERNATIONAL", "today_count": 150}]
        db.upsert_country_activity_batch(rows_v1)
        db.upsert_country_activity_batch(rows_v2)
        assert len(db.country_activity) == 1
        assert db.country_activity[0]["today_count"] == 150

    def test_empty_batch(self):
        db = InMemoryDb()
        assert db.upsert_country_activity_batch([]) == 0


class TestAnalysisClaimsPersistence:
    def test_insert_analysis_claims_returns_count(self):
        """P2-C5: persist validation claims from Anti-Hal."""
        db = InMemoryDb()
        rows = [
            {
                "claim_type": "DEVIATION",
                "claim_data": {"country": "RU", "level": "red"},
                "verdict": "PUBLISH",
                "confidence": 0.8,
                "quality_score": 0.9,
            },
            {
                "claim_type": "COORDINATION",
                "claim_data": {"countries": ["RU", "CN"], "theme": "ANTI_NATO"},
                "verdict": "ESCALATE",
                "confidence": 0.6,
                "quality_score": 0.7,
            },
        ]
        inserted = db.insert_analysis_claims(rows)
        assert inserted == 2
        assert len(db.analysis_claims) == 2

    def test_insert_analysis_escalated(self):
        """P2-C4: escalations were silently dropped in Phase 1."""
        db = InMemoryDb()
        db.insert_analysis_escalated(
            claim_id=None,
            claim_type="COORDINATION",
            escalation_reason="RU+CN+IR triple coordination detected",
            severity="HIGH",
        )
        assert len(db.analysis_escalated) == 1
        row = db.analysis_escalated[0]
        assert row["claim_type"] == "COORDINATION"
        assert row["severity"] == "HIGH"
        assert row["review_status"] == "PENDING"
        assert "RU+CN+IR" in row["escalation_reason"]

    def test_escalation_reason_truncated_at_4096(self):
        """CHECK constraint limits escalation_reason to 4096 bytes."""
        db = InMemoryDb()
        long_reason = "x" * 5000
        db.insert_analysis_escalated(
            claim_id=None,
            claim_type="DEVIATION",
            escalation_reason=long_reason,
            severity="URGENT",
        )
        assert len(db.analysis_escalated[0]["escalation_reason"]) == 4096


class TestSchemaVersion:
    def test_inmemory_returns_required_version(self):
        """P2-C9: InMemoryDb simulates a correctly migrated DB."""
        db = InMemoryDb()
        assert db.get_schema_version() == REQUIRED_SCHEMA_VERSION

    def test_required_version_is_2_or_higher(self):
        """Phase 2 = schema version 2. Future phases will bump this."""
        assert REQUIRED_SCHEMA_VERSION >= 2


class TestVerifyWritePermission:
    def test_inmemory_is_always_writable(self):
        """InMemoryDb has no permission boundaries."""
        db = InMemoryDb()
        db.verify_write_permission()  # should not raise


class TestRecordPipelineRun:
    def test_record_pipeline_run_new_signature(self):
        """P2-H7: record_pipeline_run accepts outcome and error_message."""
        db = InMemoryDb()
        db.record_pipeline_run(
            started_at=123.0,
            elapsed_seconds=45.5,
            stats={"countries_queried": 4},
            outcome="SUCCESS",
        )
        assert len(db.pipeline_runs) == 1
        row = db.pipeline_runs[0]
        assert row["outcome"] == "SUCCESS"
        assert row["elapsed_seconds"] == 45.5
        assert row["stats"]["countries_queried"] == 4

    def test_record_pipeline_run_with_error(self):
        db = InMemoryDb()
        db.record_pipeline_run(
            started_at=0.0,
            elapsed_seconds=12.3,
            stats={},
            outcome="FAILED",
            error_message="Storage quota exceeded",
        )
        assert db.pipeline_runs[0]["outcome"] == "FAILED"
        assert db.pipeline_runs[0]["error_message"] == "Storage quota exceeded"


class TestCheckStorageQuota:
    def test_inmemory_quota_is_zero(self):
        db = InMemoryDb()
        used_bytes, fraction = db.check_storage_quota()
        assert used_bytes == 0
        assert fraction == 0.0

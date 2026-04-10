"""Supabase client wrapper.

Thin layer over the official `supabase` Python client. Reads connection
details from environment variables (SUPABASE_URL + SUPABASE_SECRET_KEY)
so the credentials never live in the codebase.

Pipeline modules call into this module rather than touching supabase
directly. That keeps the rest of the pipeline mockable in unit tests
(see tests/test_db.py for the FakeDb pattern) and lets us swap the
implementation later if we move off Supabase.

Phase 2 red team fixes applied:
  - P2-C1: insert_articles batches at 2000 rows (avoid 6 MB payload limit)
  - P2-C2: upsert_country_activity_batch for 100-row batches
  - P2-C5: insert_analysis_claim + insert_analysis_escalated
  - P2-C6: raise PipelineError on silent failures (was: `except: return (0, 0.0)`)
  - P2-C9: get_schema_version() for pre-flight check
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import Any, Iterable

logger = logging.getLogger(__name__)

ENV_URL = "SUPABASE_URL"
ENV_KEY_PRIMARY = "SUPABASE_SECRET_KEY"
ENV_KEY_FALLBACKS = ("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY", "SUPABASE_ANON_KEY")

# Minimum schema version required by this pipeline code
REQUIRED_SCHEMA_VERSION = 2

# Batch sizes (Phase 2 red team fixes)
# - Supabase API has a 6 MB payload limit. Articles average ~1.5 KB each,
#   so 2000 rows = ~3 MB per batch (safe with headroom).
# - country_activity rows are smaller (~500 bytes with JSONB), 100 per batch
#   keeps round-trip count low without hitting payload limit.
ARTICLES_BATCH_SIZE = 2000
COUNTRY_ACTIVITY_BATCH_SIZE = 100
ANALYSIS_CLAIMS_BATCH_SIZE = 500


class DbError(Exception):
    """Raised when the Supabase wrapper encounters an unrecoverable error.

    Pipeline callers should catch this and decide whether to raise
    PipelineError (hard fail) or continue (best-effort operations).
    """


def _resolve_credentials() -> tuple[str, str]:
    """Read connection details from the environment.

    Raises:
        RuntimeError if required env vars are missing.
    """
    url = os.environ.get(ENV_URL, "").strip()
    key = os.environ.get(ENV_KEY_PRIMARY, "").strip()
    if not key:
        for fallback in ENV_KEY_FALLBACKS:
            key = os.environ.get(fallback, "").strip()
            if key:
                break
    if not url or not key:
        raise RuntimeError(
            f"Supabase credentials missing. Set {ENV_URL} and {ENV_KEY_PRIMARY} "
            "(or one of: " + ", ".join(ENV_KEY_FALLBACKS) + ")."
        )
    return url, key


def _new_client():
    """Lazy-import + construct a supabase Client. Stub-friendly for tests."""
    try:
        from supabase import Client, create_client
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "supabase is not installed. Install with `pip install supabase>=2.5.0`."
        ) from exc

    url, key = _resolve_credentials()
    client: Client = create_client(url, key)
    return client


# ---------------------------------------------------------------------------
# Real Supabase wrapper
# ---------------------------------------------------------------------------
class SupabaseDb:
    """Wraps the supabase client with the small set of operations the pipeline needs."""

    def __init__(self, client=None):
        self._client = client  # may be None until first use (lazy)

    def _get_client(self):
        if self._client is None:
            self._client = _new_client()
        return self._client

    # ---- write ops ----
    def insert_articles(self, records: Iterable[dict[str, Any]]) -> int:
        """Insert article rows in batches to avoid Supabase API payload limits.

        P2-C1 FIX: Supabase API has a 6 MB request body limit. At ~1.5 KB per
        article, batching at 2000 rows = ~3 MB per batch with headroom.

        Uses upsert so re-running the pipeline within the same hour doesn't
        error on the unique URL constraint.

        Returns the number of rows attempted (success count; failures raise).
        """
        rows = list(records)
        if not rows:
            return 0

        client = self._get_client()
        total = 0
        for i in range(0, len(rows), ARTICLES_BATCH_SIZE):
            batch = rows[i:i + ARTICLES_BATCH_SIZE]
            try:
                client.table("articles").upsert(batch, on_conflict="url").execute()
                total += len(batch)
            except Exception as exc:
                raise DbError(
                    f"insert_articles failed on batch {i // ARTICLES_BATCH_SIZE + 1} "
                    f"({len(batch)} rows, starting at row {i}): {exc}"
                ) from exc
        return total

    def upsert_country_activity(self, row: dict[str, Any]) -> None:
        """Insert or update a single (country, date, audience_type) row.

        Kept for backward compatibility with old callers. NEW CODE should
        use upsert_country_activity_batch for efficiency (see P2-C2).
        """
        self.upsert_country_activity_batch([row])

    def upsert_country_activity_batch(self, rows: list[dict[str, Any]]) -> int:
        """Batch upsert country_activity rows (P2-C2 fix).

        Original code made 500+ individual API calls per pipeline run,
        consuming ~25% of the 50-minute time budget just on network latency.
        Batching at 100 rows drops this to 5-10 calls.
        """
        if not rows:
            return 0
        client = self._get_client()
        total = 0
        for i in range(0, len(rows), COUNTRY_ACTIVITY_BATCH_SIZE):
            batch = rows[i:i + COUNTRY_ACTIVITY_BATCH_SIZE]
            try:
                client.table("country_activity").upsert(
                    batch, on_conflict="country,date,audience_type"
                ).execute()
                total += len(batch)
            except Exception as exc:
                raise DbError(
                    f"upsert_country_activity_batch failed on batch "
                    f"{i // COUNTRY_ACTIVITY_BATCH_SIZE + 1} "
                    f"({len(batch)} rows): {exc}"
                ) from exc
        return total

    def upsert_outlets(self, rows: Iterable[dict[str, Any]]) -> int:
        """Seed/refresh the outlet_classification table from outlets.json.

        Batched at the same size as articles for consistency.
        """
        rows_list = list(rows)
        if not rows_list:
            return 0
        client = self._get_client()
        total = 0
        for i in range(0, len(rows_list), ARTICLES_BATCH_SIZE):
            batch = rows_list[i:i + ARTICLES_BATCH_SIZE]
            try:
                client.table("outlet_classification").upsert(
                    batch, on_conflict="domain"
                ).execute()
                total += len(batch)
            except Exception as exc:
                raise DbError(
                    f"upsert_outlets failed on batch starting at row {i}: {exc}"
                ) from exc
        return total

    def insert_coordination_event(self, row: dict[str, Any]) -> None:
        client = self._get_client()
        try:
            client.table("coordination_events").insert(row).execute()
        except Exception as exc:
            raise DbError(
                f"insert_coordination_event failed for theme={row.get('theme')}: {exc}"
            ) from exc

    def upsert_daily_snapshot(self, row: dict[str, Any]) -> None:
        client = self._get_client()
        try:
            client.table("daily_snapshots").upsert(row, on_conflict="date").execute()
        except Exception as exc:
            raise DbError(
                f"upsert_daily_snapshot failed for date={row.get('date')}: {exc}"
            ) from exc

    # ---- Anti-Hallucination Agent persistence (P2-C4, P2-C5) ----

    def insert_analysis_claims(self, rows: list[dict[str, Any]]) -> int:
        """Persist validation claims from the Anti-Hallucination Agent.

        P2-C5 FIX: Previously, `validate_batch_*` computed rich ValidationResult
        metadata (hypotheses, assumptions, red team flags) and THREW IT AWAY.
        This method is how those results actually land in the DB for audit.
        """
        if not rows:
            return 0
        client = self._get_client()
        total = 0
        for i in range(0, len(rows), ANALYSIS_CLAIMS_BATCH_SIZE):
            batch = rows[i:i + ANALYSIS_CLAIMS_BATCH_SIZE]
            try:
                client.table("analysis_claims").insert(batch).execute()
                total += len(batch)
            except Exception as exc:
                # Analysis claims are a best-effort audit trail — log and continue
                # rather than crashing the whole pipeline over a missing audit row.
                logger.error(
                    "insert_analysis_claims failed on batch starting at row %d: %s",
                    i, exc,
                )
        return total

    def insert_analysis_escalated(
        self,
        claim_id: int | None,
        claim_type: str,
        escalation_reason: str,
        severity: str = "HIGH",
    ) -> None:
        """Persist an escalation to analysis_escalated (P2-C4 fix).

        Previously, ESCALATE verdicts were silently dropped. Now every
        escalated claim lands here for human review (via dashboard or
        email digest).
        """
        client = self._get_client()
        row = {
            "claim_id": claim_id,
            "claim_type": claim_type,
            "escalation_reason": escalation_reason[:4096],  # match CHECK constraint
            "severity": severity,
            "review_status": "PENDING",
        }
        try:
            client.table("analysis_escalated").insert(row).execute()
        except Exception as exc:
            # Log loudly but don't crash the pipeline — escalation persistence
            # is critical but not hard-blocking.
            logger.error(
                "insert_analysis_escalated failed (claim_type=%s): %s",
                claim_type, exc,
            )

    # ---- Schema versioning (P2-C9) ----

    def get_schema_version(self) -> int:
        """Return the highest applied schema version from the schema_version table.

        Returns 0 if the table doesn't exist or is empty — used by the pipeline's
        pre-flight check to fail fast on unmigrated databases.
        """
        client = self._get_client()
        try:
            resp = (
                client.table("schema_version")
                .select("version")
                .order("version", desc=True)
                .limit(1)
                .execute()
            )
            if resp.data:
                return int(resp.data[0].get("version", 0))
            return 0
        except Exception as exc:
            # Table doesn't exist = schema not initialized = version 0
            logger.warning("schema_version probe failed (schema may be uninitialized): %s", exc)
            return 0

    # ---- read ops ----
    def daily_article_counts(
        self,
        country: str,
        audience_type: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Return [{"date": ..., "count": ...}] for the country/audience window.

        Implementation notes:
            * supabase-py doesn't have native GROUP BY, so we fetch matching
              rows and aggregate in Python. For the small windows we use
              (max 30 days, ~5K rows/day worst case) this is fine.
            * The function returns daily totals — one row per day in range.
        """
        client = self._get_client()
        resp = (
            client.table("articles")
            .select("pub_date")
            .eq("source_country", country)
            .eq("audience_type", audience_type)
            .gte("pub_date", start_date.isoformat())
            .lte("pub_date", end_date.isoformat() + "T23:59:59")
            .execute()
        )
        rows = resp.data or []
        buckets: dict[str, int] = {}
        for r in rows:
            ts = r.get("pub_date") or ""
            day = ts[:10]  # YYYY-MM-DD prefix
            if day:
                buckets[day] = buckets.get(day, 0) + 1
        return [{"date": k, "count": v} for k, v in sorted(buckets.items())]

    def get_baseline(self, country: str, audience_type: str, target_date: date):
        """Convenience: defer to fetch_baseline (avoids a circular import at top)."""
        from .baselines import fetch_baseline

        return fetch_baseline(self, country=country, audience_type=audience_type,
                              target_date=target_date)

    # ---- health / ops ----
    def check_storage_quota(self) -> tuple[int, float]:
        """Return (used_bytes, fraction_of_free_tier).

        Queries Supabase for the row counts in the main tables and estimates
        storage usage. Uses count="estimated" (P2-H12 fix) to avoid expensive
        full-table scans every hour.

        For a precise number, query `pg_database_size(current_database())`
        from the SQL Editor.

        Raises:
            DbError if the probe itself fails (network down, RLS blocks, etc.)
            This was previously swallowed as (0, 0.0) which hid real issues.
        """
        client = self._get_client()
        try:
            # P2-H12: count="estimated" uses table statistics (fast),
            # not a full table scan like count="exact"
            articles_resp = client.table("articles").select("id", count="estimated").limit(1).execute()
            activity_resp = client.table("country_activity").select("country", count="estimated").limit(1).execute()
            articles_count = articles_resp.count or 0
            activity_count = activity_resp.count or 0
        except Exception as exc:
            raise DbError(
                f"check_storage_quota probe failed — Supabase may be unreachable "
                f"or RLS is blocking reads: {exc}"
            ) from exc

        # Rough size estimates (in bytes) per row — tuned for the MVP schema:
        # - articles row: ~1.5 KB (url + title + metadata)
        # - country_activity row: ~2 KB (JSONB fields for themes and outlets)
        est_bytes = (articles_count * 1500) + (activity_count * 2000)
        # Add 40% overhead for indexes, WAL, bloat, etc.
        est_bytes = int(est_bytes * 1.4)
        fraction = est_bytes / (500 * 1024 * 1024)
        return (est_bytes, fraction)

    def verify_write_permission(self) -> None:
        """Smoke test that the service role key can read from all critical tables.

        Raises DbError if any table is unreachable. Called by the pipeline's
        pre-flight check to fail fast BEFORE querying GDELT for 30 minutes.

        We use SELECT (not INSERT) because:
        1. It's non-destructive
        2. RLS policies apply to SELECT too (if RLS is enabled we'll see it)
        3. Supabase service_role bypasses RLS anyway, so failure means config issue
        """
        client = self._get_client()
        required_tables = [
            "outlet_classification",
            "articles",
            "country_activity",
            "coordination_events",
            "pipeline_runs",
            "analysis_claims",
            "analysis_escalated",
            "schema_version",
        ]
        for table in required_tables:
            try:
                client.table(table).select("*").limit(1).execute()
            except Exception as exc:
                raise DbError(
                    f"Cannot access table '{table}'. Either it doesn't exist "
                    f"(run schema.sql in Supabase SQL Editor) or RLS is blocking "
                    f"the service role key: {exc}"
                ) from exc

    def record_pipeline_run(
        self,
        started_at: float,
        elapsed_seconds: float,
        stats: dict[str, Any],
        outcome: str = "SUCCESS",
        error_message: str | None = None,
    ) -> None:
        """Write a row to the pipeline_runs table for health monitoring.

        P2-H7: Dropped the useless `started_at_monotonic` column (process-local
        clock, meaningless across runs). `started_at` is still accepted as the
        Python monotonic clock reading for elapsed_seconds context, but only
        `started_at_utc` lands in the DB.

        The frontend reads this to display the "last updated" timestamp.
        If this table hasn't been created yet, silently swallow the error.
        """
        client = self._get_client()
        row = {
            "started_at_utc": datetime.utcnow().isoformat() + "Z",
            "elapsed_seconds": elapsed_seconds,
            "stats": stats,
            "outcome": outcome,
            "error_message": error_message[:8192] if error_message else None,
        }
        try:
            client.table("pipeline_runs").insert(row).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("record_pipeline_run: table not available (%s)", exc)


# ---------------------------------------------------------------------------
# Dry-run / in-memory stand-in for local testing without Supabase
# ---------------------------------------------------------------------------
class InMemoryDb:
    """Drop-in replacement for SupabaseDb that records writes in lists.

    Used by `--dry-run` and unit tests. Implements the same interface as
    SupabaseDb so the rest of the pipeline doesn't need to know which one
    it's holding.
    """

    def __init__(self):
        self.articles: list[dict[str, Any]] = []
        self.country_activity: list[dict[str, Any]] = []
        self.outlets: list[dict[str, Any]] = []
        self.coordination_events: list[dict[str, Any]] = []
        self.daily_snapshots: list[dict[str, Any]] = []
        self.analysis_claims: list[dict[str, Any]] = []
        self.analysis_escalated: list[dict[str, Any]] = []
        self.pipeline_runs: list[dict[str, Any]] = []
        # Simulated schema version for dry-run
        self._schema_version = REQUIRED_SCHEMA_VERSION

    def insert_articles(self, records: Iterable[dict[str, Any]]) -> int:
        rows = list(records)
        self.articles.extend(rows)
        return len(rows)

    def upsert_country_activity(self, row: dict[str, Any]) -> None:
        """Single-row compatibility shim — delegates to batch method."""
        self.upsert_country_activity_batch([row])

    def upsert_country_activity_batch(self, rows: list[dict[str, Any]]) -> int:
        for row in rows:
            key = (row.get("country"), row.get("date"), row.get("audience_type"))
            self.country_activity = [
                r for r in self.country_activity
                if (r.get("country"), r.get("date"), r.get("audience_type")) != key
            ]
            self.country_activity.append(row)
        return len(rows)

    def upsert_outlets(self, rows: Iterable[dict[str, Any]]) -> int:
        rows_list = list(rows)
        self.outlets.extend(rows_list)
        return len(rows_list)

    def insert_coordination_event(self, row: dict[str, Any]) -> None:
        self.coordination_events.append(row)

    def upsert_daily_snapshot(self, row: dict[str, Any]) -> None:
        d = row.get("date")
        self.daily_snapshots = [r for r in self.daily_snapshots if r.get("date") != d]
        self.daily_snapshots.append(row)

    def daily_article_counts(
        self,
        country: str,
        audience_type: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        buckets: dict[str, int] = {}
        for a in self.articles:
            if a.get("source_country") != country:
                continue
            if a.get("audience_type") != audience_type:
                continue
            ts = a.get("pub_date") or ""
            day = ts[:10]
            if not day:
                continue
            try:
                day_obj = datetime.strptime(day, "%Y-%m-%d").date()
            except ValueError:
                continue
            if start_date <= day_obj <= end_date:
                buckets[day] = buckets.get(day, 0) + 1
        return [{"date": k, "count": v} for k, v in sorted(buckets.items())]

    def get_baseline(self, country: str, audience_type: str, target_date: date):
        from .baselines import fetch_baseline

        return fetch_baseline(self, country=country, audience_type=audience_type,
                              target_date=target_date)

    # ---- health / ops (matching SupabaseDb interface) ----
    def check_storage_quota(self) -> tuple[int, float]:
        """InMemoryDb always has plenty of room; return (0 bytes, 0%)."""
        return (0, 0.0)

    def verify_write_permission(self) -> None:
        """InMemoryDb is always writable — no-op."""
        return None

    def get_schema_version(self) -> int:
        """Return simulated schema version for dry-run."""
        return self._schema_version

    def record_pipeline_run(
        self,
        started_at: float,
        elapsed_seconds: float,
        stats: dict[str, Any],
        outcome: str = "SUCCESS",
        error_message: str | None = None,
    ) -> None:
        """Record a pipeline run in memory for test assertions."""
        self.pipeline_runs.append({
            "elapsed_seconds": elapsed_seconds,
            "stats": dict(stats),
            "outcome": outcome,
            "error_message": error_message,
        })

    # ---- Anti-Hallucination Agent persistence (matching SupabaseDb) ----
    def insert_analysis_claims(self, rows: list[dict[str, Any]]) -> int:
        self.analysis_claims.extend(rows)
        return len(rows)

    def insert_analysis_escalated(
        self,
        claim_id: int | None,
        claim_type: str,
        escalation_reason: str,
        severity: str = "HIGH",
    ) -> None:
        self.analysis_escalated.append({
            "claim_id": claim_id,
            "claim_type": claim_type,
            "escalation_reason": escalation_reason[:4096],
            "severity": severity,
            "review_status": "PENDING",
        })


def make_db(dry_run: bool = False) -> "SupabaseDb | InMemoryDb":
    """Factory: return an InMemoryDb when dry-run is set, otherwise SupabaseDb."""
    if dry_run:
        logger.info("DB factory: returning InMemoryDb (dry-run mode)")
        return InMemoryDb()
    return SupabaseDb()


__all__ = [
    "SupabaseDb",
    "InMemoryDb",
    "DbError",
    "make_db",
    "ENV_URL",
    "ENV_KEY_PRIMARY",
    "REQUIRED_SCHEMA_VERSION",
    "ARTICLES_BATCH_SIZE",
    "COUNTRY_ACTIVITY_BATCH_SIZE",
]

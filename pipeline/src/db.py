"""Supabase client wrapper.

Thin layer over the official `supabase` Python client. Reads connection
details from environment variables (SUPABASE_URL + SUPABASE_SECRET_KEY)
so the credentials never live in the codebase.

Pipeline modules call into this module rather than touching supabase
directly. That keeps the rest of the pipeline mockable in unit tests
(see tests/test_db.py for the FakeDb pattern) and lets us swap the
implementation later if we move off Supabase.
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
        """Insert article rows. Uses upsert so re-running the pipeline within
        the same hour doesn't error on the unique URL constraint.

        Returns the number of rows attempted.
        """
        rows = list(records)
        if not rows:
            return 0
        client = self._get_client()
        # supabase-py uses .upsert(..., on_conflict="url") for ON CONFLICT
        client.table("articles").upsert(rows, on_conflict="url").execute()
        return len(rows)

    def upsert_country_activity(self, row: dict[str, Any]) -> None:
        """Insert or update a single (country, date, audience_type) row."""
        client = self._get_client()
        client.table("country_activity").upsert(
            row, on_conflict="country,date,audience_type"
        ).execute()

    def upsert_outlets(self, rows: Iterable[dict[str, Any]]) -> int:
        """Seed/refresh the outlet_classification table from outlets.json."""
        rows_list = list(rows)
        if not rows_list:
            return 0
        client = self._get_client()
        client.table("outlet_classification").upsert(rows_list, on_conflict="domain").execute()
        return len(rows_list)

    def insert_coordination_event(self, row: dict[str, Any]) -> None:
        client = self._get_client()
        client.table("coordination_events").insert(row).execute()

    def upsert_daily_snapshot(self, row: dict[str, Any]) -> None:
        client = self._get_client()
        client.table("daily_snapshots").upsert(row, on_conflict="date").execute()

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
        storage usage. This is approximate — actual disk usage depends on
        indexes, overhead, and compression — but good enough for a 500 MB
        free tier guard.

        For a precise number, query `pg_database_size(current_database())`
        from the SQL editor and update the estimate.
        """
        client = self._get_client()
        try:
            # count=exact gives us the row count without transferring data
            articles_resp = client.table("articles").select("id", count="exact").limit(1).execute()
            activity_resp = client.table("country_activity").select("country", count="exact").limit(1).execute()
            articles_count = articles_resp.count or 0
            activity_count = activity_resp.count or 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("check_storage_quota probe failed: %s", exc)
            return (0, 0.0)

        # Rough size estimates (in bytes) per row — tuned for the MVP schema:
        # - articles row: ~1.5 KB (url + title + metadata)
        # - country_activity row: ~2 KB (JSONB fields for themes and outlets)
        est_bytes = (articles_count * 1500) + (activity_count * 2000)
        # Add 40% overhead for indexes, WAL, bloat, etc.
        est_bytes = int(est_bytes * 1.4)
        fraction = est_bytes / (500 * 1024 * 1024)
        return (est_bytes, fraction)

    def record_pipeline_run(
        self,
        started_at: float,
        elapsed_seconds: float,
        stats: dict[str, Any],
    ) -> None:
        """Write a row to the pipeline_runs table for health monitoring.

        The frontend reads this to display the "last updated" timestamp.
        If this table hasn't been created yet, silently swallow the error
        (the pipeline shouldn't fail just because health logging is missing).
        """
        client = self._get_client()
        row = {
            "started_at_monotonic": started_at,
            "started_at_utc": datetime.utcnow().isoformat() + "Z",
            "elapsed_seconds": elapsed_seconds,
            "stats": stats,
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

    def insert_articles(self, records: Iterable[dict[str, Any]]) -> int:
        rows = list(records)
        self.articles.extend(rows)
        return len(rows)

    def upsert_country_activity(self, row: dict[str, Any]) -> None:
        # Replace existing row with the same composite key
        key = (row.get("country"), row.get("date"), row.get("audience_type"))
        self.country_activity = [
            r for r in self.country_activity
            if (r.get("country"), r.get("date"), r.get("audience_type")) != key
        ]
        self.country_activity.append(row)

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

    def record_pipeline_run(
        self,
        started_at: float,
        elapsed_seconds: float,
        stats: dict[str, Any],
    ) -> None:
        """Record a pipeline run in memory for test assertions."""
        if not hasattr(self, "pipeline_runs"):
            self.pipeline_runs = []
        self.pipeline_runs.append({
            "started_at_monotonic": started_at,
            "elapsed_seconds": elapsed_seconds,
            "stats": dict(stats),
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
    "make_db",
    "ENV_URL",
    "ENV_KEY_PRIMARY",
]

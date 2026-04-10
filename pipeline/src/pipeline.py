"""Main pipeline orchestration.

The hourly pipeline performs these steps:

    1. Load the outlet/country reference data.
    2. Determine which countries to query (default: all monitored countries).
    3. For each country, query GDELT for the last N hours of articles.
    4. Classify each article's audience.
    5. Insert article rows into Supabase.
    6. For each (country, audience_type), recalculate the 30-day baseline,
       compute today's deviation ratio + level, and upsert country_activity.
    7. Aggregate theme spikes and run coordination detection.
    8. Persist coordination events.
    9. Record pipeline run metadata (PIPE health monitoring).

Red team fixes (PIPE-C1, PIPE-C2, PIPE-C3):

  - PIPE-C1: Failures in any write phase now raise PipelineError so the
    process exits non-zero. No more silent "logged-and-continue" that
    leaves corrupted state and reports success.

  - PIPE-C2: Pre-flight storage quota check against Supabase free tier.
    If approaching the 500 MB limit, the pipeline refuses to run and
    raises StorageQuotaError so operators are alerted.

  - PIPE-C3: Hard time budget. Pipeline tracks wall-clock time and aborts
    if it will overshoot the 50-minute budget (hourly cron must finish
    before the next one fires).

This module exposes a single function, `run_pipeline`, which the CLI script
(`scripts/run_pipeline.py`) calls. Everything is parameterized so a unit test
can pass a fake DB and a fake GDELT client.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable, Iterable

from .antihal import (
    Verdict,
    validate_batch_classifications,
    validate_batch_coordinations,
    validate_batch_deviations,
)
from .baselines import fetch_baseline
from .classifier import Article, classify_audience
from .countries import fips_to_iso, iso_to_fips
from .coordination import ThemeSpike, detect_coordination
from .db import InMemoryDb, SupabaseDb, make_db
from .deviation import calculate_deviation
from .outlets import get_monitored_countries
from .themes import aggregate_themes, extract_themes

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions — raised on CRITICAL failures so the process exits non-zero
# ---------------------------------------------------------------------------
class PipelineError(Exception):
    """Raised when a pipeline phase fails and the run cannot complete safely."""


class StorageQuotaError(PipelineError):
    """Raised when Supabase storage is too close to the 500 MB free tier cap."""


class TimeBudgetExceeded(PipelineError):
    """Raised when the pipeline wall-clock time exceeds the budget."""


# ---------------------------------------------------------------------------
# Budget & quota thresholds
# ---------------------------------------------------------------------------
# Hard time budget: pipeline must finish in 50 min so the next hourly cron
# has a 10-min buffer before it fires. This prevents concurrent runs.
DEFAULT_TIME_BUDGET_SECONDS = 50 * 60  # 50 minutes

# Storage quota guards for Supabase free tier (500 MB).
# Warn at 70%, refuse to write at 90%.
SUPABASE_FREE_TIER_BYTES = 500 * 1024 * 1024  # 500 MB
STORAGE_WARNING_THRESHOLD = 0.70
STORAGE_HARD_STOP_THRESHOLD = 0.90


def _check_time_budget(started_at: float, budget: float, phase: str) -> None:
    """Raise TimeBudgetExceeded if we've blown the wall-clock budget."""
    elapsed = time.monotonic() - started_at
    if elapsed > budget:
        raise TimeBudgetExceeded(
            f"Pipeline exceeded {budget:.0f}s budget in phase '{phase}' "
            f"(elapsed: {elapsed:.1f}s). Aborting to avoid overlap with next cron run."
        )


# ---------------------------------------------------------------------------
# Result objects
# ---------------------------------------------------------------------------
@dataclass
class PipelineStats:
    countries_queried: int = 0
    articles_received: int = 0
    articles_classified: int = 0
    articles_inserted: int = 0
    domestic_count: int = 0
    international_count: int = 0
    diaspora_count: int = 0
    unknown_count: int = 0
    baselines_calculated: int = 0
    country_activity_rows: int = 0
    coordination_events: int = 0
    # Anti-Hallucination Agent validation stats
    classifications_suppressed: int = 0
    deviations_suppressed: int = 0
    coordinations_suppressed: int = 0
    coordinations_escalated: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "countries_queried": self.countries_queried,
            "articles_received": self.articles_received,
            "articles_classified": self.articles_classified,
            "articles_inserted": self.articles_inserted,
            "domestic_count": self.domestic_count,
            "international_count": self.international_count,
            "diaspora_count": self.diaspora_count,
            "unknown_count": self.unknown_count,
            "baselines_calculated": self.baselines_calculated,
            "country_activity_rows": self.country_activity_rows,
            "coordination_events": self.coordination_events,
            "classifications_suppressed": self.classifications_suppressed,
            "deviations_suppressed": self.deviations_suppressed,
            "coordinations_suppressed": self.coordinations_suppressed,
            "coordinations_escalated": self.coordinations_escalated,
        }


@dataclass
class PipelineResult:
    stats: PipelineStats
    articles: list[dict[str, Any]] = field(default_factory=list)
    country_activity: list[dict[str, Any]] = field(default_factory=list)
    coordination_events: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _gdelt_row_to_article(row: dict[str, Any]) -> Article:
    """GDELT returns FIPS country codes; the rest of the pipeline uses ISO 3166-1 alpha-2.

    Translate at the boundary so internal modules can assume ISO codes throughout.
    """
    article = Article.from_gdelt_row(row)
    if article.source_country and len(article.source_country) == 2:
        # Try ISO first; if not in our table, try FIPS->ISO.
        if not _is_known_iso(article.source_country):
            iso = fips_to_iso(article.source_country)
            if iso:
                article.source_country = iso
    return article


def _is_known_iso(code: str) -> bool:
    """Cheap probe — does this 2-letter code appear in our country index?"""
    from .countries import get_country  # local import to avoid cycle
    return get_country(code) is not None


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _normalize_pub_date(value: Any) -> str:
    """Coerce a GDELT seendate (YYYYMMDDhhmmss or ISO) into ISO 8601 with TZ."""
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    # GDELT seendate format: YYYYMMDDhhmmss
    if len(s) == 14 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}T{s[8:10]}:{s[10:12]}:{s[12:14]}+00:00"
    return s


def _persist_validation_batch(
    db: Any,
    validations: list[Any],  # list[ValidationResult]
    dry_run: bool,
    *,
    only_non_publish: bool = False,
) -> None:
    """Persist Anti-Hal validation results to analysis_claims + analysis_escalated.

    P2-C4/C5 fix: previously the validate_batch_* functions computed rich
    ValidationResult metadata (hypotheses, assumptions, red team flags) and
    THREW IT AWAY. Now every claim lands in analysis_claims for audit, and
    every ESCALATE verdict lands in analysis_escalated for human review.

    Args:
        only_non_publish: if True, only persist claims with verdict != PUBLISH.
            Used for high-volume CLASSIFICATION claims (~5K per run) where
            PUBLISH rows would blow out the free tier storage for low audit value.

    Failures are logged but don't crash the pipeline — the audit trail is
    best-effort and shouldn't take down the whole run.
    """
    if dry_run or not validations:
        return

    to_persist = validations
    if only_non_publish:
        to_persist = [v for v in validations if v.verdict != Verdict.PUBLISH]

    if not to_persist:
        return

    # Convert ValidationResults to analysis_claims row shapes
    claim_rows: list[dict[str, Any]] = []
    for vr in to_persist:
        claim_rows.append({
            "claim_type": vr.claim_type,
            "claim_data": vr.claim_data,
            "quality_score": round(vr.quality_score, 3),
            "competing_hypotheses": vr.competing_hypotheses or None,
            "assumptions": vr.assumptions or None,
            "red_team_flags": vr.red_team_flags or None,
            "verdict": vr.verdict.value,
            "verdict_reason": (vr.verdict_reason or "")[:4096] or None,
            "confidence": round(vr.confidence, 3),
        })

    if hasattr(db, "insert_analysis_claims"):
        try:
            db.insert_analysis_claims(claim_rows)
        except Exception as exc:  # noqa: BLE001
            logger.error("insert_analysis_claims failed (continuing): %s", exc)

    # Escalations: one insert per ESCALATE verdict.
    # 4+ country coordination events are URGENT severity.
    if hasattr(db, "insert_analysis_escalated"):
        for vr in to_persist:
            if vr.verdict != Verdict.ESCALATE:
                continue
            severity = "HIGH"
            if vr.claim_type == "COORDINATION":
                countries = vr.claim_data.get("countries", [])
                if isinstance(countries, list) and len(countries) >= 4:
                    severity = "URGENT"
            try:
                db.insert_analysis_escalated(
                    claim_id=None,  # Phase B will wire up returned IDs
                    claim_type=vr.claim_type,
                    escalation_reason=(
                        vr.verdict_reason or "High-impact claim requires human review"
                    ),
                    severity=severity,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("insert_analysis_escalated failed: %s", exc)


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------
def run_pipeline(
    *,
    countries: list[str] | None = None,
    hours: int = 1,
    dry_run: bool = False,
    db: SupabaseDb | InMemoryDb | None = None,
    gdelt_query_country: Callable[..., Any] | None = None,
    target_date: date | None = None,
    log_to_stdout_print: bool = True,
    time_budget_seconds: float = DEFAULT_TIME_BUDGET_SECONDS,
) -> PipelineResult:
    """Execute the full pipeline.

    Args:
        countries: ISO 3166-1 alpha-2 codes to query. Defaults to every country
            with at least one outlet in outlets.json.
        hours: GDELT query window in hours.
        dry_run: when True, no writes hit Supabase. The function still prints
            the would-be actions and returns the result.
        db: optional pre-built DB handle. Tests use this to inject InMemoryDb.
        gdelt_query_country: optional callable to override the GDELT client.
            Signature: `(country_fips, hours) -> GdeltQueryResult`. Tests use
            this to avoid network calls.
        target_date: the day used for baseline / activity rows. Defaults to today (UTC).
        log_to_stdout_print: also print the headline metrics to stdout (used by
            the CLI for human-readable output).
        time_budget_seconds: hard wall-clock budget. Default 50 min (10 min
            buffer before next hourly cron fires).

    Returns:
        PipelineResult with stats + the rows it produced.

    Raises:
        PipelineError: any CRITICAL failure that leaves state corrupted.
        StorageQuotaError: Supabase approaching 500 MB free-tier cap.
        TimeBudgetExceeded: pipeline would overshoot the hourly cron window.
    """
    started_at = time.monotonic()
    target_day = target_date or _today_utc()

    # 1. Resolve query targets
    if countries:
        target_countries = sorted({c.upper() for c in countries})
    else:
        target_countries = sorted(get_monitored_countries())

    # 2. Build / accept DB handle
    if db is None:
        db = make_db(dry_run=dry_run)

    # 2a. P2-C9: schema version pre-flight check (real Supabase only).
    # Fail fast if the DB hasn't had the latest shared/schema.sql applied,
    # rather than 30 minutes into the run.
    if not dry_run and hasattr(db, "get_schema_version"):
        try:
            from .db import REQUIRED_SCHEMA_VERSION
            version = db.get_schema_version()
            if version < REQUIRED_SCHEMA_VERSION:
                raise PipelineError(
                    f"Schema version {version} is too old "
                    f"(pipeline requires >= {REQUIRED_SCHEMA_VERSION}). "
                    f"Re-run shared/schema.sql in the Supabase SQL Editor."
                )
            logger.info(
                "Schema version %d meets minimum %d",
                version, REQUIRED_SCHEMA_VERSION,
            )
        except PipelineError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Schema version probe failed: %s", exc)

    # 2b. PIPE-C2: storage quota pre-flight check (real Supabase only)
    if not dry_run and hasattr(db, "check_storage_quota"):
        try:
            used_bytes, used_fraction = db.check_storage_quota()
            logger.info(
                "Supabase storage: %.1f MB used (%.1f%% of 500 MB free tier)",
                used_bytes / (1024 * 1024),
                used_fraction * 100,
            )
            if used_fraction >= STORAGE_HARD_STOP_THRESHOLD:
                raise StorageQuotaError(
                    f"Supabase storage at {used_fraction * 100:.1f}% of free tier "
                    f"({used_bytes / (1024 * 1024):.1f} MB / 500 MB). "
                    f"Refusing to write. Purge old articles or upgrade to Pro."
                )
            if used_fraction >= STORAGE_WARNING_THRESHOLD:
                logger.warning(
                    "Supabase storage approaching free tier limit (%.1f%% used). "
                    "Will hit hard stop at %.0f%%.",
                    used_fraction * 100, STORAGE_HARD_STOP_THRESHOLD * 100,
                )
        except StorageQuotaError:
            raise
        except Exception as exc:  # noqa: BLE001
            # Quota check itself failed (not ideal, but don't block the pipeline
            # on a quota probe failure — log loudly instead).
            logger.warning("Storage quota pre-flight check failed: %s", exc)

    # 3. Resolve the GDELT client
    if gdelt_query_country is None:
        from .gdelt_client import query_country as default_query
        gdelt_query_country = default_query

    stats = PipelineStats(countries_queried=len(target_countries))
    result = PipelineResult(stats=stats)

    if log_to_stdout_print:
        print(f"Querying GDELT for {len(target_countries)} countries...")

    # 4. Query GDELT, classify each article, batch into article rows
    article_rows: list[dict[str, Any]] = []
    # For coordination + theme aggregation we keep per-country rollups in memory
    by_country_audience: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    theme_buckets: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for iso2 in target_countries:
        # PIPE-C3: time budget check before each country query
        _check_time_budget(started_at, time_budget_seconds, phase=f"query_country({iso2})")

        fips = iso_to_fips(iso2) or iso2  # if no mapping, use ISO as a fallback
        try:
            qresult = gdelt_query_country(fips, hours=hours)
        except Exception as exc:  # noqa: BLE001
            logger.warning("GDELT query failed for %s (%s): %s", iso2, fips, exc)
            continue

        df = getattr(qresult, "df", None)
        if df is None or (hasattr(df, "empty") and df.empty):
            logger.debug("No articles for %s", iso2)
            continue

        # Convert DataFrame rows to dicts (so the test fakes can pass plain lists too)
        if hasattr(df, "to_dict"):
            rows = df.to_dict(orient="records")
        else:
            rows = list(df)

        stats.articles_received += len(rows)

        for raw in rows:
            try:
                article = _gdelt_row_to_article(raw)
                # Force the GDELT-reported country to ISO for consistency
                if not article.source_country:
                    article.source_country = iso2
                audience, confidence = classify_audience(article)
                stats.articles_classified += 1
                if audience == "DOMESTIC":
                    stats.domestic_count += 1
                elif audience == "INTERNATIONAL":
                    stats.international_count += 1
                elif audience == "DIASPORA":
                    stats.diaspora_count += 1
                else:
                    stats.unknown_count += 1

                themes = extract_themes(raw)
                row = {
                    "url": article.url,
                    "title_original": article.title,
                    "source_domain": article.domain,
                    "source_country": article.source_country or iso2,
                    "source_language": article.language or None,
                    "audience_type": audience,
                    "audience_confidence": confidence,
                    "tone": float(raw.get("tone") or 0.0),
                    "pub_date": _normalize_pub_date(raw.get("seendate") or article.pub_date),
                    "gdelt_themes": themes,
                }
                article_rows.append(row)
                key = (row["source_country"], row["audience_type"])
                by_country_audience[key].append(row)
                for theme in themes:
                    theme_buckets[key][theme] += 1
            except Exception as exc:  # noqa: BLE001
                logger.debug("Skipping unparseable GDELT row: %s", exc)
                continue

    print(
        f"Classified {stats.domestic_count} articles as DOMESTIC, "
        f"{stats.international_count} as INTERNATIONAL, "
        f"{stats.diaspora_count} as DIASPORA, "
        f"{stats.unknown_count} as UNKNOWN"
    )

    # 4b. Anti-Hallucination Agent: validate classifications
    # UNKNOWN classifications get suppressed; low-confidence get caveats.
    article_rows, class_validations = validate_batch_classifications(article_rows)
    stats.classifications_suppressed = sum(
        1 for v in class_validations if v.verdict == Verdict.SUPPRESS
    )
    if stats.classifications_suppressed > 0:
        print(
            f"Anti-Hal: suppressed {stats.classifications_suppressed} "
            f"low-confidence classifications"
        )

    # P2-C5: persist non-PUBLISH classification claims to analysis_claims.
    # PUBLISH classifications are high-volume and low audit value, skip to
    # keep storage usage reasonable on the 500 MB free tier.
    _persist_validation_batch(db, class_validations, dry_run, only_non_publish=True)

    # 5. Insert articles (PIPE-C1: fail-fast instead of log-and-continue)
    if dry_run:
        print(f"DRY RUN: would insert {len(article_rows)} article rows into Supabase")
    else:
        _check_time_budget(started_at, time_budget_seconds, phase="insert_articles")
        try:
            inserted = db.insert_articles(article_rows)
            stats.articles_inserted = inserted
            if article_rows and inserted == 0:
                raise PipelineError(
                    f"insert_articles returned 0 for {len(article_rows)} rows — "
                    "Supabase may be rejecting writes. Aborting."
                )
        except PipelineError:
            raise
        except Exception as exc:
            logger.error("Failed to insert articles: %s", exc)
            raise PipelineError(f"Article insertion failed: {exc}") from exc
    result.articles = article_rows

    # 6. Recalculate baselines + compute today's deviation per (country, audience)
    activity_rows: list[dict[str, Any]] = []
    spike_records: list[ThemeSpike] = []
    for (country, audience), articles_in_bucket in by_country_audience.items():
        baseline = fetch_baseline(db, country=country, audience_type=audience,
                                  target_date=target_day)
        stats.baselines_calculated += 1

        deviation = calculate_deviation(len(articles_in_bucket), baseline)

        # Top theme list for the country page
        themes_for_bucket = aggregate_themes(articles_in_bucket)
        top_themes_sorted = sorted(themes_for_bucket.items(), key=lambda x: x[1], reverse=True)[:10]

        # Top outlets for the country page
        outlet_counter: dict[str, int] = defaultdict(int)
        for a in articles_in_bucket:
            outlet_counter[a["source_domain"]] += 1
        top_outlets = sorted(outlet_counter.items(), key=lambda x: x[1], reverse=True)[:10]

        row = {
            "country": country,
            "date": target_day.isoformat(),
            "audience_type": audience,
            "today_count": deviation.today_count,
            "baseline_mean": deviation.baseline_mean,
            "baseline_std": deviation.baseline_std,
            "deviation_ratio": deviation.ratio,
            "z_score": deviation.z_score,
            "level": deviation.level,
            "confidence": deviation.confidence,
            "cold_start": False,  # anti-hal may flip this to True
            "top_themes": dict(top_themes_sorted),
            "top_outlets": [{"domain": d, "count": c} for d, c in top_outlets],
            # Internal-only: consumed by validate_deviation for cold start detection,
            # stripped before DB write (not a schema column).
            "days_sampled": deviation.days_sampled,
        }
        activity_rows.append(row)
        result.country_activity.append(row)

        # Build spike records for coordination detection
        for theme, count in top_themes_sorted:
            if baseline.is_usable and baseline.mean > 0:
                ratio = count / baseline.mean
            else:
                ratio = 0.0
            spike_records.append(
                ThemeSpike(
                    country=country,
                    theme=theme,
                    article_count=count,
                    baseline=baseline.mean,
                    ratio=ratio,
                )
            )

    # 6b. Anti-Hallucination Agent: validate deviations
    # Extreme levels (red/deepBlue) with LOW baseline confidence get suppressed.
    activity_rows, dev_validations = validate_batch_deviations(activity_rows)
    stats.deviations_suppressed = sum(
        1 for v in dev_validations if v.verdict == Verdict.SUPPRESS
    )
    if stats.deviations_suppressed > 0:
        print(
            f"Anti-Hal: suppressed {stats.deviations_suppressed} "
            f"extreme-but-low-confidence deviations"
        )
    # Rebuild result.country_activity from the validated rows
    result.country_activity = list(activity_rows)

    # P2-C5: persist all deviation claims (low volume, high audit value)
    _persist_validation_batch(db, dev_validations, dry_run)

    # Strip internal-only fields before DB write:
    # - anything _-prefixed (anti-hal caveats, etc.)
    # - days_sampled (not a schema column; used only by the validator)
    _INTERNAL_ACTIVITY_FIELDS = {"days_sampled"}
    db_activity_rows = [
        {
            k: v for k, v in row.items()
            if not k.startswith("_") and k not in _INTERNAL_ACTIVITY_FIELDS
        }
        for row in activity_rows
    ]

    if dry_run:
        print(f"DRY RUN: would upsert {len(db_activity_rows)} rows to country_activity")
    else:
        _check_time_budget(started_at, time_budget_seconds, phase="upsert_country_activity")
        # P2-C2: batch upsert instead of 500+ individual API calls.
        # PIPE-C1: fail-fast on any error — partial success leaves state corrupt.
        try:
            inserted = db.upsert_country_activity_batch(db_activity_rows)
            stats.country_activity_rows = inserted
            if db_activity_rows and inserted == 0:
                raise PipelineError(
                    f"upsert_country_activity_batch returned 0 for "
                    f"{len(db_activity_rows)} rows — Supabase may be rejecting writes."
                )
        except PipelineError:
            raise
        except Exception as exc:
            logger.error("Failed to batch upsert country_activity: %s", exc)
            raise PipelineError(
                f"country_activity batch upsert failed for "
                f"{len(db_activity_rows)} rows: {exc}"
            ) from exc
    print(f"Calculated baselines for {stats.baselines_calculated} (country, audience) pairs")
    print(f"Computed deviations for {len(activity_rows)} (country, audience) pairs")

    # 7. Coordination detection
    _check_time_budget(started_at, time_budget_seconds, phase="coordination_detection")
    coord_events = detect_coordination(spike_records, time_window_hours=24)
    raw_coord_rows: list[dict[str, Any]] = []
    for event in coord_events:
        raw_coord_rows.append({
            "date": target_day.isoformat(),
            "theme": event.theme,
            "countries": event.countries,
            "coordination_score": round(event.score, 3),
            "time_window_hours": event.time_window_hours,
            "details": event.details,
        })

    # 7b. Anti-Hallucination Agent: validate coordination events.
    # This is the most aggressive suppressor — Phase A kills almost everything
    # that could be a major event, wire syndication, or anniversary pattern.
    validated_coord_rows, coord_validations = validate_batch_coordinations(raw_coord_rows)
    stats.coordination_events = len(validated_coord_rows)
    stats.coordinations_suppressed = sum(
        1 for v in coord_validations if v.verdict == Verdict.SUPPRESS
    )
    stats.coordinations_escalated = sum(
        1 for v in coord_validations if v.verdict == Verdict.ESCALATE
    )
    if stats.coordinations_suppressed > 0 or stats.coordinations_escalated > 0:
        print(
            f"Anti-Hal: suppressed {stats.coordinations_suppressed}, "
            f"escalated {stats.coordinations_escalated} "
            f"coordination events (of {len(raw_coord_rows)} detected)"
        )

    # P2-C4/C5: persist ALL coordination claims (publish + suppress + escalate)
    # Coordination events are low volume and high audit value — keep them all.
    _persist_validation_batch(db, coord_validations, dry_run)

    failed_coord_writes: list[tuple[str, str]] = []
    for ev_row in validated_coord_rows:
        # Strip anti-hal internal fields before DB write
        clean_row = {k: v for k, v in ev_row.items() if not k.startswith("_")}
        result.coordination_events.append(clean_row)
        if dry_run:
            continue
        try:
            db.insert_coordination_event(clean_row)
        except Exception as exc:  # noqa: BLE001
            failed_coord_writes.append((clean_row.get("theme", "?"), str(exc)))
            logger.error(
                "Failed to insert coordination event %s: %s",
                clean_row.get("theme"), exc,
            )

    # Coordination failures are non-fatal (coordination is best-effort; a failure
    # here doesn't corrupt anything downstream) but still get logged loudly.
    if failed_coord_writes and not dry_run:
        logger.error(
            "Coordination event write failures: %d of %d (continuing)",
            len(failed_coord_writes), len(coord_events),
        )

    if dry_run:
        print(f"DRY RUN: would insert {len(validated_coord_rows)} coordination events (validated)")
    else:
        print(f"Published {len(validated_coord_rows)} coordination events (after Anti-Hal validation)")

    # 9. Record successful run metadata for health monitoring
    if not dry_run and hasattr(db, "record_pipeline_run"):
        try:
            db.record_pipeline_run(
                started_at=started_at,
                elapsed_seconds=time.monotonic() - started_at,
                stats=stats.to_dict(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to record pipeline run metadata: %s", exc)

    return result


__all__ = [
    "run_pipeline",
    "PipelineStats",
    "PipelineResult",
    "PipelineError",
    "StorageQuotaError",
    "TimeBudgetExceeded",
    "DEFAULT_TIME_BUDGET_SECONDS",
]

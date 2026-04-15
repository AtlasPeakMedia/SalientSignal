-- SalientSignal — Supabase database schema (Phase 2 hardened)
-- Source: SalientSignal-Algorithms.md "Database Schema (Core Tables)"
-- Constraint: Free tier (Supabase 500 MB) — purge articles >30 days manually.
--
-- Phase 2 red team fixes applied (from proud-jumping-key.md Phase 2 Deep Plan):
--   P2-C8 (revised by migration 003): ENABLE RLS on all tables. No policies defined,
--          so anon role (publishable key) gets blocked at PostgREST. Service role
--          bypasses RLS, so the pipeline + Next.js server keep full access.
--   P2-C9: schema_version table + pre-flight check
--   P2-C4: analysis_escalated table (ESCALATE claims no longer silently dropped)
--   P2-H7: DROP started_at_monotonic (useless process-local clock)
--   P2-H8: TEXT column size constraints (prevent DoS via malformed GDELT article)
--   Drop useless implicit unique index on articles.url → explicit named index
--
-- To apply: paste into Supabase SQL Editor, run. Safe to re-run (all IF NOT EXISTS).

------------------------------------------------------------------
-- 0. Schema version table (used by pipeline pre-flight check)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_version (
    version             INT PRIMARY KEY,
    applied_at          TIMESTAMPTZ DEFAULT NOW(),
    notes               TEXT
);
-- Phase 2 schema = version 2. Phase 1 was version 1 (informal, never shipped).
INSERT INTO schema_version (version, notes)
VALUES (2, 'Phase 2: RLS disabled, escalation table, size constraints, batched upserts')
ON CONFLICT (version) DO NOTHING;

------------------------------------------------------------------
-- 1. Source classification (seeded from outlets.json by seed_outlets.py)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outlet_classification (
    domain              TEXT PRIMARY KEY,
    country             CHAR(2) NOT NULL,                -- ISO 3166-1 alpha-2
    audience_type       TEXT NOT NULL,                   -- DOMESTIC | INTERNATIONAL | DIASPORA
    outlet_name         TEXT NOT NULL,
    outlet_type         TEXT,                            -- NEWS_AGENCY | TV | RADIO | NEWSPAPER | DIGITAL
    languages           TEXT[],                          -- ISO 639-1 codes
    is_state_owned      BOOLEAN DEFAULT FALSE,
    is_state_aligned    BOOLEAN DEFAULT FALSE,
    confidence          DOUBLE PRECISION DEFAULT 1.0,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT outlet_audience_check
        CHECK (audience_type IN ('DOMESTIC', 'INTERNATIONAL', 'DIASPORA')),
    CONSTRAINT outlet_name_size
        CHECK (octet_length(outlet_name) <= 1024),
    CONSTRAINT outlet_notes_size
        CHECK (notes IS NULL OR octet_length(notes) <= 4096),
    CONSTRAINT outlet_domain_size
        CHECK (octet_length(domain) <= 253)              -- max DNS name length
);
CREATE INDEX IF NOT EXISTS idx_outlets_country ON outlet_classification(country);
CREATE INDEX IF NOT EXISTS idx_outlets_audience ON outlet_classification(audience_type);
ALTER TABLE outlet_classification ENABLE ROW LEVEL SECURITY;

------------------------------------------------------------------
-- 2. Articles (rolling 30 days, GDELT-sourced)
--    Note: url uniqueness is enforced via explicit named index
--    (P2-H: make the uniqueness contract explicit so it survives migrations)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS articles (
    id                  BIGSERIAL PRIMARY KEY,
    url                 TEXT NOT NULL,
    title_original      TEXT,
    source_domain       TEXT NOT NULL,
    source_country      CHAR(2) NOT NULL,                -- ISO 3166-1 alpha-2
    source_language     CHAR(2),                         -- ISO 639-1 (kept short to match GDELT)
    audience_type       TEXT NOT NULL,
    audience_confidence DOUBLE PRECISION,
    tone                DOUBLE PRECISION,                -- GDELT tone score, -10..+10
    pub_date            TIMESTAMPTZ NOT NULL,
    ingested_at         TIMESTAMPTZ DEFAULT NOW(),
    gdelt_themes        TEXT[],                          -- GDELT theme codes
    CONSTRAINT articles_audience_check
        CHECK (audience_type IN ('DOMESTIC', 'INTERNATIONAL', 'DIASPORA')),
    -- P2-H8: Prevent DoS via malformed GDELT article with huge title
    CONSTRAINT articles_title_size
        CHECK (title_original IS NULL OR octet_length(title_original) <= 65536),
    CONSTRAINT articles_url_size
        CHECK (octet_length(url) <= 8192)
);
-- Explicit unique index on url (survives migrations, documents intent)
CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_url_unique ON articles(url);
CREATE INDEX IF NOT EXISTS idx_articles_country_date ON articles(source_country, pub_date DESC);
-- P2-H4: composite index for daily_article_counts() query (WHERE country AND audience_type AND pub_date BETWEEN)
CREATE INDEX IF NOT EXISTS idx_articles_src_aud_date
    ON articles(source_country, audience_type, pub_date DESC);
CREATE INDEX IF NOT EXISTS idx_articles_domain ON articles(source_domain);
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;

------------------------------------------------------------------
-- 3. Country activity (one row per country/date/audience_type — drives globe)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS country_activity (
    country             CHAR(2) NOT NULL,
    date                DATE NOT NULL,
    audience_type       TEXT NOT NULL,
    today_count         INT NOT NULL DEFAULT 0,
    baseline_mean       DOUBLE PRECISION,                -- 30-day mean
    baseline_std        DOUBLE PRECISION,                -- 30-day std dev
    deviation_ratio     DOUBLE PRECISION,                -- today / baseline_mean
    z_score             DOUBLE PRECISION,                -- (today - mean) / std
    level               TEXT,                            -- deepBlue|steelBlue|coolGray|neutral|amber|orange|red
    confidence          TEXT,                            -- LOW | MEDIUM | HIGH
    -- P2-H4: Cold start indicator for frontend "warming up" banner
    cold_start          BOOLEAN DEFAULT FALSE,
    top_themes          JSONB,                           -- {theme_code: count}
    top_outlets         JSONB,                           -- [{domain, count}]
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (country, date, audience_type),
    CONSTRAINT country_activity_audience_check
        CHECK (audience_type IN ('DOMESTIC', 'INTERNATIONAL', 'DIASPORA'))
);
CREATE INDEX IF NOT EXISTS idx_country_activity_date ON country_activity(date DESC);
ALTER TABLE country_activity ENABLE ROW LEVEL SECURITY;

------------------------------------------------------------------
-- 4. Coordination events (cross-country narrative coordination)
--    Only PUBLISH + PUBLISH_WITH_CAVEAT events land here.
--    ESCALATE events go to analysis_escalated (below).
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS coordination_events (
    id                  BIGSERIAL PRIMARY KEY,
    detected_at         TIMESTAMPTZ DEFAULT NOW(),
    date                DATE NOT NULL,
    theme               TEXT NOT NULL,
    countries           TEXT[] NOT NULL,                 -- ISO 3166-1 alpha-2 codes
    coordination_score  DOUBLE PRECISION NOT NULL,       -- 0.0 - 1.0
    time_window_hours   INT DEFAULT 24,
    caveat              TEXT,                            -- hedge language if PUBLISH_WITH_CAVEAT
    details             JSONB                            -- per-country counts, ratios
);
CREATE INDEX IF NOT EXISTS idx_coordination_date ON coordination_events(date DESC);
CREATE INDEX IF NOT EXISTS idx_coordination_theme ON coordination_events(theme);
ALTER TABLE coordination_events ENABLE ROW LEVEL SECURITY;

------------------------------------------------------------------
-- 5. Daily snapshots (kept forever, tiny footprint, drives historical view)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_snapshots (
    date                DATE PRIMARY KEY,
    total_articles      INT,
    countries_active    INT,
    country_activity    JSONB,                           -- aggregated per-country day rollup
    theme_counts        JSONB,                           -- {theme: count}
    coordinations       JSONB,                           -- list of coordination events
    silences            JSONB,                           -- countries below baseline
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE daily_snapshots ENABLE ROW LEVEL SECURITY;

------------------------------------------------------------------
-- 6. Pipeline runs (health monitoring — drives "last updated" banner)
--    P2-H7: Dropped started_at_monotonic (useless process-local clock)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  BIGSERIAL PRIMARY KEY,
    started_at_utc      TIMESTAMPTZ NOT NULL,
    elapsed_seconds     DOUBLE PRECISION,
    stats               JSONB,                           -- PipelineStats.to_dict()
    outcome             TEXT DEFAULT 'SUCCESS',          -- SUCCESS | PARTIAL | FAILED
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT pipeline_outcome_check
        CHECK (outcome IN ('SUCCESS', 'PARTIAL', 'FAILED')),
    CONSTRAINT pipeline_error_size
        CHECK (error_message IS NULL OR octet_length(error_message) <= 8192)
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at_utc DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_outcome ON pipeline_runs(outcome);
ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;

------------------------------------------------------------------
-- 7. Analysis claims — every claim the pipeline makes, tagged with verdict
--    from the Anti-Hallucination Agent (SAT-based validation layer)
--    P2-C5: pipeline now actually persists here (was silently discarded)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis_claims (
    id                  BIGSERIAL PRIMARY KEY,
    claim_type          TEXT NOT NULL,                   -- CLASSIFICATION | DEVIATION | COORDINATION | AI_TEXT
    claim_data          JSONB NOT NULL,                  -- the claim itself
    source_refs         JSONB,                           -- which articles/outputs were the evidence
    quality_score       DOUBLE PRECISION,                -- Quality of Information Check score (0.0-1.0)
    competing_hypotheses JSONB,                          -- ACH: alternative explanations
    assumptions         JSONB,                           -- Key Assumptions Check output
    red_team_flags      JSONB,                           -- Red team: how could this be wrong?
    verdict             TEXT NOT NULL,                   -- PUBLISH | PUBLISH_WITH_CAVEAT | SUPPRESS | ESCALATE
    verdict_reason      TEXT,
    confidence          DOUBLE PRECISION,                -- final confidence after validation
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT analysis_verdict_check
        CHECK (verdict IN ('PUBLISH', 'PUBLISH_WITH_CAVEAT', 'SUPPRESS', 'ESCALATE')),
    -- Size constraints to prevent runaway JSONB (anti-hal metadata can be large)
    CONSTRAINT claims_claim_data_size
        CHECK (octet_length(claim_data::text) <= 16384),
    CONSTRAINT claims_hypotheses_size
        CHECK (competing_hypotheses IS NULL OR octet_length(competing_hypotheses::text) <= 32768),
    CONSTRAINT claims_verdict_reason_size
        CHECK (verdict_reason IS NULL OR octet_length(verdict_reason) <= 4096)
);
CREATE INDEX IF NOT EXISTS idx_claims_type ON analysis_claims(claim_type);
CREATE INDEX IF NOT EXISTS idx_claims_verdict ON analysis_claims(verdict);
CREATE INDEX IF NOT EXISTS idx_claims_created ON analysis_claims(created_at DESC);
ALTER TABLE analysis_claims ENABLE ROW LEVEL SECURITY;

------------------------------------------------------------------
-- 8. Suppressed claims audit (claims the anti-hal agent killed)
--    Used for manual review and algorithm tuning.
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis_suppressed (
    id                  BIGSERIAL PRIMARY KEY,
    claim_id            BIGINT REFERENCES analysis_claims(id) ON DELETE CASCADE,
    suppression_reason  TEXT NOT NULL,                   -- which SAT killed it + why
    manual_review_status TEXT DEFAULT 'PENDING',         -- PENDING | OVERRIDE_PUBLISH | CONFIRMED_SUPPRESS
    reviewer_notes      TEXT,
    reviewed_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT suppressed_review_status_check
        CHECK (manual_review_status IN ('PENDING', 'OVERRIDE_PUBLISH', 'CONFIRMED_SUPPRESS')),
    CONSTRAINT suppressed_reason_size
        CHECK (octet_length(suppression_reason) <= 4096)
);
CREATE INDEX IF NOT EXISTS idx_suppressed_status ON analysis_suppressed(manual_review_status);
ALTER TABLE analysis_suppressed ENABLE ROW LEVEL SECURITY;

------------------------------------------------------------------
-- 9. Analysis escalated (CRITICAL addition — P2-C4)
--    High-impact claims flagged for human review.
--    Previously these were silently dropped by validate_batch_*.
--    This table is the queue the frontend/email digest will read from.
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis_escalated (
    id                  BIGSERIAL PRIMARY KEY,
    claim_id            BIGINT REFERENCES analysis_claims(id) ON DELETE CASCADE,
    claim_type          TEXT NOT NULL,                   -- CLASSIFICATION | DEVIATION | COORDINATION | AI_TEXT
    escalation_reason   TEXT NOT NULL,
    severity            TEXT DEFAULT 'HIGH',             -- LOW | MEDIUM | HIGH | URGENT
    review_status       TEXT DEFAULT 'PENDING',          -- PENDING | CONFIRMED | REJECTED | STALE
    reviewer_notes      TEXT,
    reviewed_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT escalated_severity_check
        CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')),
    CONSTRAINT escalated_review_status_check
        CHECK (review_status IN ('PENDING', 'CONFIRMED', 'REJECTED', 'STALE')),
    CONSTRAINT escalated_reason_size
        CHECK (octet_length(escalation_reason) <= 4096)
);
CREATE INDEX IF NOT EXISTS idx_escalated_status ON analysis_escalated(review_status);
CREATE INDEX IF NOT EXISTS idx_escalated_created ON analysis_escalated(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_escalated_severity ON analysis_escalated(severity);
ALTER TABLE analysis_escalated ENABLE ROW LEVEL SECURITY;

------------------------------------------------------------------
-- 11. Country theme rollups (Session 31 — GKG 2.0 bulk ingestion)
------------------------------------------------------------------
-- Populated by pipeline/scripts/run_gkg_backfill.py which downloads GKG 2.0
-- bulk CSV files from data.gdeltproject.org (separate CDN from the DOC API),
-- filters rows to our monitored domains, and aggregates themes by
-- (country, audience_type, period, theme).
--
-- Three period granularities, same schema. The SCAME dashboard queries
-- whichever matches the user's selected time window.
--
-- Storage budget estimate (15 months historical):
--   monthly:  ~80 countries × 2 audiences × 15 months × 50 themes = 120,000 rows
--   weekly:   ~80 countries × 2 audiences × 65 weeks × 50 themes  = 520,000 rows
--   daily:    ~80 countries × 2 audiences × 464 days × 30 themes  = 2,227,200 rows
-- At ~200 B/row: ~575 MB for all three. That's over the free tier.
--
-- Strategy: ship monthly + weekly now. Daily is opt-in and only backfilled
-- for the last 30 days (not all 15 months) so it fits in the budget.

CREATE TABLE IF NOT EXISTS country_theme_monthly (
    country             CHAR(2) NOT NULL,
    audience_type       TEXT NOT NULL,
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    theme               TEXT NOT NULL,
    article_count       INT NOT NULL DEFAULT 0,
    bucket_total        INT NOT NULL DEFAULT 0,
    share               DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_tone            DOUBLE PRECISION,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (country, audience_type, period_start, theme),
    CONSTRAINT theme_monthly_audience_check
        CHECK (audience_type IN ('DOMESTIC', 'INTERNATIONAL', 'DIASPORA')),
    CONSTRAINT theme_monthly_counts_positive
        CHECK (article_count >= 0 AND bucket_total >= 0),
    CONSTRAINT theme_monthly_share_range
        CHECK (share >= 0 AND share <= 1),
    CONSTRAINT theme_monthly_theme_size
        CHECK (octet_length(theme) <= 256),
    CONSTRAINT theme_monthly_period_order
        CHECK (period_end >= period_start)
);
CREATE INDEX IF NOT EXISTS idx_theme_monthly_country_period
    ON country_theme_monthly(country, period_start DESC);
CREATE INDEX IF NOT EXISTS idx_theme_monthly_period
    ON country_theme_monthly(period_start DESC, period_end DESC);
CREATE INDEX IF NOT EXISTS idx_theme_monthly_theme_lookup
    ON country_theme_monthly(theme, period_start DESC);
ALTER TABLE country_theme_monthly ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS country_theme_weekly (
    country             CHAR(2) NOT NULL,
    audience_type       TEXT NOT NULL,
    period_start        DATE NOT NULL,                   -- ISO week Monday
    period_end          DATE NOT NULL,                   -- ISO week Sunday
    theme               TEXT NOT NULL,
    article_count       INT NOT NULL DEFAULT 0,
    bucket_total        INT NOT NULL DEFAULT 0,
    share               DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_tone            DOUBLE PRECISION,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (country, audience_type, period_start, theme),
    CONSTRAINT theme_weekly_audience_check
        CHECK (audience_type IN ('DOMESTIC', 'INTERNATIONAL', 'DIASPORA')),
    CONSTRAINT theme_weekly_counts_positive
        CHECK (article_count >= 0 AND bucket_total >= 0),
    CONSTRAINT theme_weekly_share_range
        CHECK (share >= 0 AND share <= 1),
    CONSTRAINT theme_weekly_theme_size
        CHECK (octet_length(theme) <= 256),
    CONSTRAINT theme_weekly_period_order
        CHECK (period_end >= period_start)
);
CREATE INDEX IF NOT EXISTS idx_theme_weekly_country_period
    ON country_theme_weekly(country, period_start DESC);
CREATE INDEX IF NOT EXISTS idx_theme_weekly_period
    ON country_theme_weekly(period_start DESC, period_end DESC);
CREATE INDEX IF NOT EXISTS idx_theme_weekly_theme_lookup
    ON country_theme_weekly(theme, period_start DESC);
ALTER TABLE country_theme_weekly ENABLE ROW LEVEL SECURITY;

-- Daily table is provisioned but only backfilled for the last 30 days.
-- Older daily data rolls up into weekly and is purged from country_theme_daily.
CREATE TABLE IF NOT EXISTS country_theme_daily (
    country             CHAR(2) NOT NULL,
    audience_type       TEXT NOT NULL,
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    theme               TEXT NOT NULL,
    article_count       INT NOT NULL DEFAULT 0,
    bucket_total        INT NOT NULL DEFAULT 0,
    share               DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_tone            DOUBLE PRECISION,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (country, audience_type, period_start, theme),
    CONSTRAINT theme_daily_audience_check
        CHECK (audience_type IN ('DOMESTIC', 'INTERNATIONAL', 'DIASPORA')),
    CONSTRAINT theme_daily_counts_positive
        CHECK (article_count >= 0 AND bucket_total >= 0),
    CONSTRAINT theme_daily_share_range
        CHECK (share >= 0 AND share <= 1),
    CONSTRAINT theme_daily_theme_size
        CHECK (octet_length(theme) <= 256),
    CONSTRAINT theme_daily_period_order
        CHECK (period_end >= period_start AND period_start = period_end)
);
CREATE INDEX IF NOT EXISTS idx_theme_daily_country_period
    ON country_theme_daily(country, period_start DESC);
CREATE INDEX IF NOT EXISTS idx_theme_daily_theme_lookup
    ON country_theme_daily(theme, period_start DESC);
ALTER TABLE country_theme_daily ENABLE ROW LEVEL SECURITY;

-- Bump schema version for the new theme tables
INSERT INTO schema_version (version, notes)
VALUES (3, 'Session 31: country_theme_monthly/weekly/daily from GKG 2.0 bulk ingestion')
ON CONFLICT (version) DO NOTHING;

------------------------------------------------------------------
-- Final check: record that schema was applied successfully
------------------------------------------------------------------
-- This INSERT will error if the schema_version table wasn't created,
-- which is a useful early signal of schema corruption.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_version WHERE version = 3) THEN
        RAISE EXCEPTION 'Schema version 3 not recorded — country_theme_* tables missing or broken';
    END IF;
END $$;

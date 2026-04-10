-- SalientSignal — Supabase database schema (MVP subset)
-- Source: SalientSignal-Algorithms.md "Database Schema (Core Tables)"
-- Constraint: Free tier (Supabase 500 MB) — purge articles >30 days, snapshots forever.
--
-- To apply: paste into Supabase SQL Editor, run.

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
    confidence          FLOAT DEFAULT 1.0,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT outlet_audience_check
        CHECK (audience_type IN ('DOMESTIC', 'INTERNATIONAL', 'DIASPORA'))
);
CREATE INDEX IF NOT EXISTS idx_outlets_country ON outlet_classification(country);
CREATE INDEX IF NOT EXISTS idx_outlets_audience ON outlet_classification(audience_type);

------------------------------------------------------------------
-- 2. Articles (rolling 30 days, GDELT-sourced)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS articles (
    id                  BIGSERIAL PRIMARY KEY,
    url                 TEXT NOT NULL UNIQUE,
    title_original      TEXT,
    source_domain       TEXT NOT NULL,
    source_country      CHAR(2) NOT NULL,                -- ISO 3166-1 alpha-2
    source_language     CHAR(2),                         -- ISO 639-1 (kept short to match GDELT)
    audience_type       TEXT NOT NULL,
    audience_confidence FLOAT,
    tone                FLOAT,                           -- GDELT tone score, -10..+10
    pub_date            TIMESTAMPTZ NOT NULL,
    ingested_at         TIMESTAMPTZ DEFAULT NOW(),
    gdelt_themes        TEXT[],                          -- GDELT theme codes
    CONSTRAINT articles_audience_check
        CHECK (audience_type IN ('DOMESTIC', 'INTERNATIONAL', 'DIASPORA'))
);
CREATE INDEX IF NOT EXISTS idx_articles_country_date ON articles(source_country, pub_date);
CREATE INDEX IF NOT EXISTS idx_articles_audience_date ON articles(audience_type, pub_date);
CREATE INDEX IF NOT EXISTS idx_articles_domain ON articles(source_domain);

------------------------------------------------------------------
-- 3. Country activity (one row per country/date/audience_type — drives globe)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS country_activity (
    country             CHAR(2) NOT NULL,
    date                DATE NOT NULL,
    audience_type       TEXT NOT NULL,
    today_count         INT NOT NULL DEFAULT 0,
    baseline_mean       FLOAT,                           -- 30-day mean
    baseline_std        FLOAT,                           -- 30-day std dev
    deviation_ratio     FLOAT,                           -- today / baseline_mean
    z_score             FLOAT,                           -- (today - mean) / std
    level               TEXT,                            -- deepBlue|steelBlue|coolGray|neutral|amber|orange|red
    confidence          TEXT,                            -- LOW | MEDIUM | HIGH
    top_themes          JSONB,                           -- {theme_code: count}
    top_outlets         JSONB,                           -- [{domain, count}]
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (country, date, audience_type),
    CONSTRAINT country_activity_audience_check
        CHECK (audience_type IN ('DOMESTIC', 'INTERNATIONAL', 'DIASPORA'))
);
CREATE INDEX IF NOT EXISTS idx_country_activity_date ON country_activity(date);

------------------------------------------------------------------
-- 4. Coordination events (cross-country narrative coordination)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS coordination_events (
    id                  SERIAL PRIMARY KEY,
    detected_at         TIMESTAMPTZ DEFAULT NOW(),
    date                DATE NOT NULL,
    theme               TEXT NOT NULL,
    countries           TEXT[] NOT NULL,                 -- ISO 3166-1 alpha-2 codes
    coordination_score  FLOAT NOT NULL,                  -- 0.0 - 1.0
    time_window_hours   INT DEFAULT 24,
    details             JSONB                            -- per-country counts, ratios
);
CREATE INDEX IF NOT EXISTS idx_coordination_date ON coordination_events(date);
CREATE INDEX IF NOT EXISTS idx_coordination_theme ON coordination_events(theme);

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

------------------------------------------------------------------
-- 6. Pipeline runs (health monitoring — drives "last updated" banner)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  BIGSERIAL PRIMARY KEY,
    started_at_monotonic DOUBLE PRECISION,                -- process-local start timestamp
    started_at_utc      TIMESTAMPTZ NOT NULL,
    elapsed_seconds     DOUBLE PRECISION,
    stats               JSONB,                            -- PipelineStats.to_dict()
    outcome             TEXT DEFAULT 'SUCCESS',           -- SUCCESS | PARTIAL | FAILED
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at_utc DESC);

------------------------------------------------------------------
-- 7. Analysis claims — every claim the pipeline makes, tagged with verdict
--    from the Anti-Hallucination Agent (SAT-based validation layer)
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis_claims (
    id                  BIGSERIAL PRIMARY KEY,
    claim_type          TEXT NOT NULL,                    -- CLASSIFICATION | DEVIATION | COORDINATION | AI_TEXT
    claim_data          JSONB NOT NULL,                   -- the claim itself (country, theme, audience, etc.)
    source_refs         JSONB,                            -- which articles/outputs were the evidence
    quality_score       FLOAT,                            -- Quality of Information Check score (0.0-1.0)
    competing_hypotheses JSONB,                           -- ACH: alternative explanations
    assumptions         JSONB,                            -- Key Assumptions Check output
    red_team_flags      JSONB,                            -- Red team: how could this be wrong?
    verdict             TEXT NOT NULL,                    -- PUBLISH | PUBLISH_WITH_CAVEAT | SUPPRESS | ESCALATE
    verdict_reason      TEXT,
    confidence          FLOAT,                            -- final confidence after validation
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT analysis_verdict_check
        CHECK (verdict IN ('PUBLISH', 'PUBLISH_WITH_CAVEAT', 'SUPPRESS', 'ESCALATE'))
);
CREATE INDEX IF NOT EXISTS idx_claims_type ON analysis_claims(claim_type);
CREATE INDEX IF NOT EXISTS idx_claims_verdict ON analysis_claims(verdict);
CREATE INDEX IF NOT EXISTS idx_claims_created ON analysis_claims(created_at DESC);

------------------------------------------------------------------
-- 8. Suppressed claims audit (claims the anti-hal agent killed)
--    Used for manual review and algorithm tuning.
------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis_suppressed (
    id                  BIGSERIAL PRIMARY KEY,
    claim_id            BIGINT REFERENCES analysis_claims(id) ON DELETE CASCADE,
    suppression_reason  TEXT NOT NULL,                    -- which SAT killed it + why
    manual_review_status TEXT DEFAULT 'PENDING',          -- PENDING | OVERRIDE_PUBLISH | CONFIRMED_SUPPRESS
    reviewer_notes      TEXT,
    reviewed_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT suppressed_review_status_check
        CHECK (manual_review_status IN ('PENDING', 'OVERRIDE_PUBLISH', 'CONFIRMED_SUPPRESS'))
);
CREATE INDEX IF NOT EXISTS idx_suppressed_status ON analysis_suppressed(manual_review_status);

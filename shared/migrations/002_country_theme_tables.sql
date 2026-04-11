-- Session 31 migration: country_theme_monthly + weekly + daily tables
--
-- Apply this in the Supabase SQL Editor. Safe to run multiple times (all
-- IF NOT EXISTS). Bumps schema_version to 3.
--
-- This is a minimal incremental migration — it contains ONLY the new
-- tables, not the full schema. Paste into Supabase SQL Editor and click
-- Run. Takes < 2 seconds.
--
-- After this migration is applied you can run:
--
--     python -m pipeline.scripts.import_gkg_backfill \
--         --input-json pipeline/data/theme_backfill_monthly.json
--
-- to push the 15-month theme backfill into country_theme_monthly.

------------------------------------------------------------------
-- country_theme_monthly
------------------------------------------------------------------
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
ALTER TABLE country_theme_monthly DISABLE ROW LEVEL SECURITY;

------------------------------------------------------------------
-- country_theme_weekly
------------------------------------------------------------------
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
ALTER TABLE country_theme_weekly DISABLE ROW LEVEL SECURITY;

------------------------------------------------------------------
-- country_theme_daily (rolling 30-day window, not full 15 months)
------------------------------------------------------------------
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
ALTER TABLE country_theme_daily DISABLE ROW LEVEL SECURITY;

------------------------------------------------------------------
-- Bump schema version
------------------------------------------------------------------
INSERT INTO schema_version (version, notes)
VALUES (3, 'Session 31: country_theme_monthly/weekly/daily from GKG 2.0 bulk ingestion')
ON CONFLICT (version) DO NOTHING;

------------------------------------------------------------------
-- Final check
------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_version WHERE version = 3) THEN
        RAISE EXCEPTION 'Schema version 3 not recorded — migration failed';
    END IF;
END $$;

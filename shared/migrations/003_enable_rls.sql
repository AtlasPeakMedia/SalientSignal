-- Migration 003: Enable Row Level Security on all public tables
--
-- WHY: Supabase Security Advisor flagged every public table as
-- `rls_disabled_in_public` (Apr 13 2026 email). Phase 2 (P2-C8) had
-- intentionally disabled RLS to prevent silent write failures from
-- restrictive default policies. The safer pattern is:
--   - ENABLE RLS on every table
--   - Define NO policies (so anon / authenticated roles get nothing)
--   - Service role bypasses RLS — pipeline + Next.js server keep working
--
-- Both the Python pipeline (pipeline/src/db.py) and the web frontend
-- (src/lib/supabase.ts) authenticate with the service-role / secret key,
-- which bypasses RLS. The anon publishable key is never used anywhere in
-- this codebase, so blocking it from PostgREST is correct and safe.
--
-- To apply: paste into Supabase SQL Editor and run. Safe to re-run.

ALTER TABLE schema_version          ENABLE ROW LEVEL SECURITY;
ALTER TABLE outlet_classification   ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles                ENABLE ROW LEVEL SECURITY;
ALTER TABLE country_activity        ENABLE ROW LEVEL SECURITY;
ALTER TABLE coordination_events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_snapshots         ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs           ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_claims         ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_suppressed     ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_escalated      ENABLE ROW LEVEL SECURITY;
ALTER TABLE country_theme_monthly   ENABLE ROW LEVEL SECURITY;
ALTER TABLE country_theme_weekly    ENABLE ROW LEVEL SECURITY;
ALTER TABLE country_theme_daily     ENABLE ROW LEVEL SECURITY;

-- Bump schema_version so the pipeline pre-flight check sees the upgrade
INSERT INTO schema_version (version, notes)
VALUES (4, 'Migration 003: RLS enabled on all tables (service role bypasses; anon blocked)')
ON CONFLICT (version) DO NOTHING;

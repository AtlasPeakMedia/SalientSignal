# Render Deployment Runbook — SalientSignal Pipeline

**Phase E17 / Phase F1 of the backfill plan.** This runbook walks you
through deploying the SalientSignal hourly pipeline to Render's free
tier cron service. Allow ~15 minutes of hands-on time plus ~30 minutes
of monitoring the first run.

---

## Before you start

**Prerequisites:**

1. Render account (free, no credit card required). https://render.com/
2. This repository pushed to the `main` branch of `AtlasPeakMedia/SalientSignal`
   on GitHub.
3. Supabase project with schema migrated to version 2+. You already have
   this from the Phase 2 initial load.
4. The backfill must be imported to Supabase BEFORE the cron fires its
   first run — otherwise the live pipeline will see an empty
   `country_activity` table and compute LOW-confidence baselines. See
   **Phase F1/F2** in the plan file for the ordered sequence:

       Phase F1: run backfill locally  →  verify JSON  →  import to Supabase
       Phase F2: deploy Render cron    (this runbook)

**Pre-flight check (recommended):** Run the local pre-flight script
before clicking anything in Render, with your production env vars set:

```bash
export SUPABASE_URL=https://<your-project>.supabase.co
export SUPABASE_SECRET_KEY=sb_secret_...
cd /path/to/SalientSignal
python pipeline/scripts/preflight_check.py
```

Expected output ends with **"All checks passed. Pipeline is ready to
deploy."** If any check fails, resolve it locally before pushing to
Render — debugging a red Render deploy is much harder than debugging a
red local pre-flight.

---

## Step 1: Import the Blueprint

1. Log into https://dashboard.render.com/
2. Click **"New +"** → **"Blueprint"** (NOT "Web Service" or "Cron Job" —
   Blueprint auto-detects `render.yaml`)
3. Connect your GitHub account if you haven't already
4. Select the `AtlasPeakMedia/SalientSignal` repository
5. Render reads `render.yaml` at the repo root and shows a preview of
   the cron service it's about to create: `salientsignal-pipeline`,
   type `cron`, schedule `7 * * * *`, free plan.
6. Click **"Apply"** to create the service.

Render begins building the Docker image. The first build takes ~3-5
minutes because it has to install pandas, numpy, gdeltdoc, and
supabase from scratch. Subsequent builds are faster thanks to layer
caching.

---

## Step 2: Paste environment variables

1. Render prompts you to fill in the two `sync: false` env vars:
   - `SUPABASE_URL`
   - `SUPABASE_SECRET_KEY`
2. Get these values from your Supabase dashboard:
   - URL: https://app.supabase.com/project/_/settings/api → **Project URL**
   - Key: same page → **service_role key** (NOT the anon key — the
     pipeline needs write access).
3. Paste both into the Render env var inputs and click **"Save"**.

> **Security note:** The service role key bypasses RLS. Treat it like a
> password. Render stores it encrypted and never exposes it in build
> logs, but if you commit it to git accidentally, you MUST rotate it
> immediately via the Supabase dashboard.

Optional env vars that have sensible defaults but you can override:

| Variable                       | Default | Notes                                         |
|--------------------------------|---------|-----------------------------------------------|
| `LOG_LEVEL`                    | `INFO`  | `DEBUG` is noisy but useful for first run     |
| `PIPELINE_TIME_BUDGET_SECONDS` | `3000`  | 50 min; lower to 2700 for extra cron overlap buffer |

---

## Step 3: Wait for the first build

Render's build log will stream in real time. Watch for:

```
✓ Building Docker image
✓ Installed gdeltdoc==1.12.0 ...
✓ Successfully installed salientsignal-pipeline-0.1.0
==> Build successful
==> Your service is live 🎉
```

If the build fails, the most common causes are:

1. **Missing dependency in `pyproject.toml`** — check Render's build log
   for the specific pip error and fix locally.
2. **Docker base image pull rate limit** — Render uses Docker Hub and
   occasionally hits the anonymous pull limit. Re-trigger the build.
3. **SUPABASE_URL or SUPABASE_SECRET_KEY missing** — Render will warn you
   at deploy time, but if you skipped step 2, the first cron tick will
   fail on the pre-flight credential check.

---

## Step 4: Trigger a manual run (recommended)

Don't wait for the scheduled `:07` tick for your first run. Trigger it
manually so you can watch the logs:

1. Render dashboard → `salientsignal-pipeline` service
2. Click **"Manual Deploy"** → **"Deploy latest commit"**
3. Watch the "Events" tab — a cron invocation starts immediately

Expected pipeline output (with `LOG_LEVEL=INFO`):

```
[pre-flight] Loaded environment from /app/pipeline/.env
[pre-flight] Running checks...
[pre-flight] ✓ Supabase credentials found (URL: https://...)
[pre-flight] ✓ Schema version 2 meets minimum 2
[pre-flight] ✓ All critical tables accessible
[pre-flight] All checks passed
Querying GDELT for 81 countries...
Classified N articles as DOMESTIC, M as INTERNATIONAL, ...
=== Pipeline complete ===
  countries_queried: 81
  articles_received: NNN
  articles_classified: NNN
  ...
  elapsed_seconds: ~200-600
```

The first live run typically takes **3-10 minutes** depending on GDELT
rate-limit headwind. It should comfortably finish inside the 50-minute
budget.

---

## Step 5: Verify the run landed in Supabase

Open the Supabase SQL Editor and run these queries:

```sql
-- Was the pipeline run recorded?
SELECT * FROM pipeline_runs ORDER BY started_at_utc DESC LIMIT 1;
-- Expected: 1 row with outcome='SUCCESS' and elapsed_seconds < 600

-- Were articles ingested in the last hour?
SELECT COUNT(*) FROM articles WHERE ingested_at > now() - interval '1 hour';
-- Expected: > 0 (exact number depends on GDELT output that hour)

-- Did the country_activity table get updated for today?
SELECT COUNT(DISTINCT country)
  FROM country_activity
  WHERE date = current_date;
-- Expected: ~70+ (all countries the pipeline touched)
```

Also visit **https://salientsignal.com/** and confirm:

1. The header badge shows **"LIVE"** (not "DEMO" or "COLD START")
2. The banner shows **"Live intelligence data"** with the 15-month
   backfill language
3. The footer shows **"LIVE DATA · HH:MM"** and the current wall clock

---

## Step 6: Monitor the first 24 hours

Render's free-tier cron service has these quirks to watch for:

| Symptom                         | Likely cause                                    | Fix                                            |
|---------------------------------|-------------------------------------------------|------------------------------------------------|
| Cron missed its :07 slot        | Render free tier backlog                        | Normal — it catches up within ~15 min         |
| Pipeline_runs shows FAILED     | GDELT rate limit OR Supabase transient error    | Check logs; usually self-heals next hour       |
| Build fails on push            | Docker cache corrupt                            | "Clear build cache & deploy" in Render dash  |
| Cron runs but no articles     | LOCKED_DOWN_COUNTRIES not firing fallback       | Check that B9 code is in the deployed image   |

---

## Rolling back a bad deploy

If a Render deploy breaks the pipeline:

1. Render dashboard → **"Events"** tab
2. Find the last known-good deploy
3. Click **"Rollback to this deploy"**
4. Render rebuilds from the earlier commit and starts running that
   version on the next cron tick.

This is much faster than reverting the git commit because Render keeps
the old image around.

---

## How the pipeline interacts with the historical backfill

After the backfill is imported (Phase F1 pre-requisite), Supabase's
`country_activity` table has:

- 15 months of historical rows with `cold_start=FALSE`, real baselines,
  and empty `top_themes` / sparse `top_outlets`
- Today's row (populated by the most-recent pre-cron manual run) with
  whatever data the live pipeline had

Once the Render cron fires, each run:

1. Pulls the last hour of GDELT articles
2. Computes deviations against the 30-day window in the `articles`
   table (which starts thin on day 1 and fills in)
3. Upserts `country_activity` for today's date — OVERWRITING whatever
   was there. On day 1 this is fine because the only pre-existing row
   for today was placeholder.

**Known caveat:** the live pipeline's `fetch_baseline()` computes from
the `articles` table, not from `country_activity`. Until that's
refactored (Phase 5 deferred item), the live pipeline's baselines
REBUILD from scratch over its first 21 days of operation. The backfill
rows for dates BEFORE the live pipeline started remain intact, so the
globe stays fully populated and the `HistoricalDataBanner` stays on
"Live intelligence data" throughout. This caveat is documented in
`pipeline/COLD_START.md` under "Historical Backfill Mode".

---

## Cost monitoring

Render free tier limits that apply to this project:

- **Cron jobs: UNLIMITED.** No monthly quota. Runs however often your
  schedule dictates.
- **Cron compute time: 500 build hours/month included.** A 5-minute run
  24 times a day = 60 hours/month. Comfortably under.
- **Bandwidth: 100 GB/month.** GDELT responses are ~10-50 KB each;
  we're nowhere near this.
- **Free services sleep after 15 min of inactivity.** Cron jobs are
  explicitly exempt from the sleep rule.

Expected cost: **$0/month**. If something changes, Render will email
you before charging anything.

---

## Reference: full file inventory for this phase

New files added in the E17 commit:

- `render.yaml`                      — Blueprint manifest (repo root)
- `pipeline/Dockerfile`              — Python 3.11-slim + pipeline install
- `pipeline/.env.example.render`     — Env var manifest with documentation
- `pipeline/scripts/preflight_check.py` — Local validation before deploy
- `docs/RENDER_DEPLOYMENT.md`        — This runbook

No pipeline source code changes. The existing `run_pipeline.py` entry
point runs unchanged inside the container.

# GKG 2.0 Theme Pipeline — Deployment Runbook

**Status:** Built + tested (Session 31, 2026-04-10 night). Not yet deployed to Supabase/Vercel — this doc is the ship-to-production checklist.

---

## What this pipeline does

Ingests **per-article theme data** for the ~300 monitored state-media outlets from GDELT's Global Knowledge Graph 2.0 bulk CSV files (separate CDN from the DOC 2.0 API that feeds the hourly pipeline), aggregates by `(country, audience_type, period, theme)`, and writes to three Supabase tables:

- `country_theme_monthly` — one row per (country, audience, month, theme) with article_count, bucket_total, share, avg_tone. 15 months of history.
- `country_theme_weekly` — same shape, ISO-week periods. Populated hourly from the current window.
- `country_theme_daily` — same shape, single-day periods. Last ~30 days only (older rolls out).

These tables power the **SCAME dashboard** on `/country/[code]` pages (two-column DOMESTIC vs INTERNATIONAL theme browser with narrative paragraphs, word-cloud pills, and 15-month sparkline drill-down) AND the **Trending Themes** panel on the home page.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              GDELT GKG 2.0 bulk CDN                             │
│     http://data.gdeltproject.org/gdeltv2/YYYYMMDDHHMMSS.csv.zip │
│              (15-min files, not rate-limited)                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP (urllib, 20x parallel for backfill)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│            pipeline/src/gkg_client.py                           │
│  • downloads zip                                                │
│  • unzips in memory                                             │
│  • tab-CSV parses each row                                      │
│  • filters to monitored domains via subdomain walk-up           │
│  • returns GkgRow[] with themes, title, tone                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│         pipeline/src/theme_aggregator.py                        │
│  • dedupe by (domain, url)                                      │
│  • resolve outlet → country + audience_type                     │
│  • bucket by (country, audience, period_start)                  │
│  • compute article_count, bucket_total, share, avg_tone         │
│  • keep top 50 themes per bucket                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
       ┌──────────────────┴──────────────────┐
       │                                     │
       ▼                                     ▼
┌──────────────────────┐          ┌──────────────────────┐
│  Historical backfill │          │  Hourly incremental  │
│                      │          │                      │
│ run_gkg_backfill.py  │          │  run_gkg_hourly.py   │
│ → writes JSON        │          │ → upserts Supabase   │
│                      │          │                      │
│ ↓                    │          │  • 75-min lookback   │
│ import_gkg_backfill  │          │  • parallelism=4     │
│ → upserts Supabase   │          │  • 240s budget       │
└──────────────────────┘          └──────────────────────┘
           │                                │
           └────────────────┬───────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  country_theme_{monthly,weekly,daily}           │
│                   (Supabase, schema v3)                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ getCountryThemes() + getTrendingThemes()
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│            Next.js server components                            │
│                                                                 │
│  /country/[code] → CountryThemePanel (SCAME dashboard)          │
│  /                → Trending Themes card                        │
└─────────────────────────────────────────────────────────────────┘
```

## Deploy sequence

### Step 1: Apply schema v3 to Supabase (2 seconds, one-time)

Log into Supabase dashboard for the `bzmhnenqrilsrlxlujak` project. Open **SQL Editor** → **New query**. Paste the contents of:

```
shared/migrations/002_country_theme_tables.sql
```

Click **Run**. Expected output: `Success. No rows returned.` in under 2 seconds. The migration is idempotent (all `CREATE TABLE IF NOT EXISTS`) so re-running is safe.

Verify with a quick query in the SQL Editor:

```sql
SELECT version, applied_at, notes FROM schema_version ORDER BY version;
```

You should see version 3 in the result set with the Session 31 notes.

### Step 2: Run the 15-month backfill (~4 hours, autonomous)

**This step is already in progress** from Session 31 — a background process is writing `pipeline/data/theme_backfill_monthly.json`. Check progress:

```bash
tail -5 "pipeline/logs/theme_backfill_monthly.log"
```

Expected completion around 4 hours after launch (2.8 files/sec × 44,544 files). When complete, the last log line will read:

```
Wrote N theme buckets to pipeline/data/theme_backfill_monthly.json (X.XX MB)
```

If you need to re-run for any reason (different date range, resume after interruption):

```bash
cd "path/to/SalientSignal"
python -m pipeline.scripts.run_gkg_backfill \
    --start-date 2025-01-01 \
    --end-date 2026-04-09 \
    --period monthly \
    --parallelism 20 \
    --output-json pipeline/data/theme_backfill_monthly.json \
    --force
```

The `--force` flag is required to overwrite an existing output file.

### Step 3: Dry-run validate the JSON (30 seconds)

Before touching Supabase, confirm the JSON is structurally valid:

```bash
python -m pipeline.scripts.import_gkg_backfill \
    --input-json pipeline/data/theme_backfill_monthly.json \
    --dry-run
```

Expected output: all 6 validation passes green. If any pass fails, the script exits non-zero with a clear error message pointing at the specific bucket row. Fix the root cause (re-run the backfill if needed) before proceeding.

### Step 4: Import to Supabase (~5-15 minutes depending on row count)

```bash
python -m pipeline.scripts.import_gkg_backfill \
    --input-json pipeline/data/theme_backfill_monthly.json \
    --interactive
```

The `--interactive` flag prompts `[y/N]` once before the first DB write so you can sanity-check the row count. Typing `y` starts the upsert.

Expected runtime: ~120,000 monthly bucket rows ÷ 500 rows/batch = ~240 batches × ~50 ms each = **~12 seconds** of actual upserts. The script also writes an import manifest JSON alongside the input file for audit traceability.

After the import finishes, verify in Supabase:

```sql
SELECT
    country,
    audience_type,
    COUNT(*) AS themes,
    MAX(period_start) AS latest_month
FROM country_theme_monthly
GROUP BY country, audience_type
ORDER BY country, audience_type
LIMIT 20;
```

You should see dozens of themes per (country, audience) pair for the most recent complete month (likely March 2026).

**The SCAME dashboard lights up the instant the upsert completes.** No Vercel redeploy needed — the data layer queries Supabase on every request (`dynamic = 'force-dynamic'` on the country pages).

### Step 5: Deploy the updated render.yaml (10 minutes, one-time)

The `render.yaml` file in the repo root now defines TWO cron services:

1. `salientsignal-pipeline` — the existing hourly data pipeline (unchanged)
2. `salientsignal-themes` — the new hourly GKG theme incremental

If you already imported the Blueprint in Render, go to the dashboard and click **"Sync Blueprint"** to pick up the new service. Render will build the Docker image, find the new cron, and schedule it automatically.

If this is a fresh Render setup:
1. Log into Render
2. **New +** → **Blueprint**
3. Connect the GitHub repo (`AtlasPeakMedia/SalientSignal`)
4. Render auto-detects `render.yaml` and shows both services
5. Paste `SUPABASE_URL` and `SUPABASE_SECRET_KEY` env vars in the dashboard for BOTH services (each `sync: false` var needs to be set on each service)
6. Click **Create Services**
7. First cron tick:
   - `salientsignal-pipeline` fires at the next `:07` past the hour
   - `salientsignal-themes` fires at the next `:17` past the hour

Monitor both services' logs in the Render dashboard for the first few runs. Expected behavior:

- `salientsignal-pipeline` — writes article rows, coordination events, country_activity updates
- `salientsignal-themes` — writes theme bucket rows for the current day/week/month

**Important**: the theme cron will log a clear warning and exit 0 on the first run if schema v3 hasn't been applied yet (Step 1). The main pipeline cron is unaffected by any theme-side failures.

### Step 6: Visual verification

- Home page (`/`) → Trending Themes card should now populate with real counts instead of the empty-state placeholder
- `/country/CN` → SCAME theme panel should show two-column DOMESTIC / INTERNATIONAL theme pills with narrative paragraphs and a period picker
- Click a pill → 15-month sparkline should appear below

Note: **IR DOMESTIC column will be empty** because GKG doesn't crawl `.ir` TLDs. This is documented in Methodology section 10 (Known limitations). Same applies to KP, CU, SY, and partial BY / VE.

## Rollback

If the import produces bad data you can roll back with a single SQL:

```sql
-- Nuke everything from a specific period onwards
DELETE FROM country_theme_monthly WHERE period_start >= '2025-01-01';
DELETE FROM country_theme_weekly  WHERE period_start >= '2025-01-01';
DELETE FROM country_theme_daily   WHERE period_start >= '2026-03-15';
```

The SCAME dashboard will instantly return to its empty state (schema still applied, just no rows). No redeploy needed.

## Known constraints

- **Supabase free tier storage**: 500 MB total. A 15-month monthly backfill is ~120K rows × ~150 B each = ~18 MB. Leaves plenty of headroom for the weekly/daily tables + the existing country_activity rows.
- **GKG CDN limits**: Google Cloud Storage on our `data.gdeltproject.org` hits. No published rate limit. Empirically we ran 44,544 downloads at parallelism=20 without a single 429. Zero cost, no authentication.
- **Render free tier**: 750 free execution hours per service per month. Two cron jobs × ~5 min each × 24 hr × 30 days = ~50 hours. Well under the limit.

## Related files

- `pipeline/src/gkg_client.py` — bulk-file downloader + parser
- `pipeline/src/theme_aggregator.py` — aggregation + bucketing math
- `pipeline/scripts/run_gkg_backfill.py` — CLI for historical backfill
- `pipeline/scripts/run_gkg_hourly.py` — hourly incremental for Render
- `pipeline/scripts/import_gkg_backfill.py` — validation + Supabase upsert
- `shared/migrations/002_country_theme_tables.sql` — schema v3 migration
- `src/lib/data.ts` (getCountryThemes, getTrendingThemes) — Next.js data layer
- `src/components/Country/CountryThemePanel.tsx` — SCAME dashboard UI
- `src/components/Country/ThemeTimelineSparkline.tsx` — 15-month sparkline
- `src/lib/theme_narrative.ts` — SCAME narrative paragraph generator
- `src/app/methodology/page.tsx` — user-facing explanation (Section 7)

---
aliases:
  - SalientSignal Theme Backfill
  - SalientSignal Date Picker
  - Theme Way Forward
tags:
  - apex
  - business
  - app
  - salientsignal
  - plan
created: 2026-04-10
---

# SalientSignal — Theme Backfill + Date Picker Plan

> **Status:** **MAJOR REVISION NEEDED — 2026-04-10 23:55.** The original plan assumed a `wordcloudthemes` mode in the GDELT DOC 2.0 API. **That mode does not exist.** See the "GDELT theme API reality" section below for the architectural finding. The plan has been revised to use GDELT GKG 2.0 bulk files as the real theme source.
> **Created:** 2026-04-10 evening (during first 15-month main backfill run, which is currently at ~150/301 outlets)
> **Depends on:** Main backfill (`TimelineVolRaw`) completing + importing first. ✅ DONE at 23:38 — 52,432 rows in Supabase.
> **Target:** User clicks a country → sees top themes discussed by that country's state media in a selectable month or week, going back to Jan 2025.

---

## ⚠️ CRITICAL FINDING (2026-04-10 23:55) — GDELT theme API reality

Spent ~30 minutes probing the GDELT DOC 2.0 API for theme modes. Discovered:

1. **The `wordcloudthemes` / `wordcloudenglishthemes` modes do NOT exist in the DOC 2.0 API.** Every attempt returns `Invalid mode.` Verified against the official blog post at https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/ — the only word cloud modes documented are `wordcloudimagetags` (for image tags only) and `wordcloudimagewebtags` (for image web tags). There is no text-theme word cloud mode.

2. **The `gdeltdoc` Python library's `timeline_search` only supports 5 modes**: `timelinevol`, `timelinevolraw`, `timelinetone`, `timelinelang`, `timelinesourcecountry`. No theme variant.

3. **The ArtList mode does NOT return theme data per article.** The response columns from `gdeltdoc.article_search()` are exactly: `url, url_mobile, title, seendate, socialimage, domain, language, sourcecountry`. No `themes`, no `gkg_themes`, no `v2themes`. This is why all 118 articles currently in Supabase have `gdelt_themes=[]` — our existing `extract_themes()` function in `pipeline/src/themes.py` is looking for fields that the DOC 2.0 API never populates. **This is a silent data-capture bug.**

4. **Where theme data actually lives:** GDELT GKG 2.0 bulk CSV files, published every 15 minutes at `http://data.gdeltproject.org/gdeltv2/YYYYMMDDHHMMSS.gkg.csv.zip`. Each file contains hundreds of thousands of articles with full theme tags (`V2Themes` column), locations, persons, organizations, tones, GCAM scores, etc. This is a **completely different ingestion path** from the DOC 2.0 API.

### What this means for the plan

The original Option A (per-outlet `wordcloudthemes` queries) is dead. There's no endpoint to call. The original Option B (sourcecountry-level `wordcloudthemes`) is also dead, same reason.

**The real architectural choices are:**

- **Option X (the one we're going with): GDELT GKG 2.0 bulk CSV files.** Download the 15-min files, filter each to rows where `SourceCommonName` matches one of our 172+ domains, extract `V2Themes`, aggregate per (country, audience, date). This is the documented, complete, historical theme source. Each file is ~5-20 MB; for our filtered domains after dedup we keep ~0.5% of rows, so storage is small. For 15 months historical: 464 days × 96 files/day = 44,544 files to download, most of them ~3s each with good parallelism = ~6 hours to ingest historical themes.

- **Option Y (complementary, not a replacement): Claude API theme classification on article titles going forward.** Cheap (~$0.001 per article with Haiku), accurate, customizable taxonomy, works for any language after translation. But requires article titles, and we only have titles for articles we ingest via DOC 2.0 ArtList mode. Historical titles are unavailable. Going forward: each daily live pipeline run could classify the day's titles through Claude, tagging them with our own narrative taxonomy (NATO_AGGRESSION, WESTERN_HYPOCRISY, SANCTIONS_PAIN, etc.) rather than GKG's 3,000+ GDELT codes.

- **Option Z (immediate short-term): Don't build theme history at all. Ship the SCAME dashboard with "themes from NOW forward only", growing daily as live pipeline runs ingest article titles.** Lowest-effort option, but gives up the historical browser that was Don's explicit ask. Only choose this if Options X and Y are both too much work for the value.

### Recommended execution order

1. **Fix the silent bug FIRST.** Remove the dead theme-extraction code path from `extract_themes()` or wire it up to a GKG 2.0 ingestion source. As written it looks for fields that never exist. Either make it work or make it error loudly when it doesn't.

2. **Build the GKG 2.0 downloader** (~200 lines of Python). Module at `pipeline/src/gkg_client.py`. Downloads one 15-min file, filters to our registered domains, returns rows with (domain, date, themes, title_en, url). Tested against 10 real files before going live.

3. **Build the theme aggregation** module (`pipeline/src/theme_aggregation.py`). Takes GKG rows, groups by (country, audience_type, month, week), outputs top 50 themes per bucket with counts.

4. **Historical GKG ingestion** (`pipeline/scripts/run_gkg_backfill.py`). Downloads 15 months of 15-min files, filters, aggregates, writes to new `country_theme_monthly` + `country_theme_weekly` tables. Estimated runtime 4-6 hours; bandwidth heavy but disk-light.

5. **Live GKG ingestion** — added to the existing Render cron job. Every hour, download the 4 files from the past hour, filter, aggregate, upsert. ~30s of work per cron tick.

6. **Start building the SCAME dashboard UI** against the new tables. Word clouds, narrative paragraphs, country × month × audience drill-down.

**Estimated total work: ~12-15 hours of Claude time across 2-3 sessions.** Don's time: zero, except for eyeballing results.

**Tonight's pivot:** I can't start any of this usefully because GDELT's servers are being rate-limited on our IP tonight (the full 15-month backfill exhausted our daily quota). GKG bulk files are served from a separate CDN (`data.gdeltproject.org` vs `api.gdeltproject.org`), so theoretically this would still work, but I don't want to start a 4-6 hour ingestion run at 11pm without user sign-off on the new architecture first. **Starting tomorrow morning** is the better move.

---

## The user request

Exact quote:

> "I want people to click on a country and see what the top issues/themes/messages discussed by state media was on XX Month in XX Year."

And in the follow-up:

> "I want it monthly and weekly. We can look at daily next week."

So the target feature is a **historical theme browser** on the country page, with monthly and weekly granularity shipping in the first iteration and daily granularity deferred to next week.

---

## Why the current backfill can't provide themes

The main backfill (running now) uses GDELT's `TimelineVolRaw` mode. That mode returns **only daily article counts per domain** — one integer per day, nothing else. It's extremely fast (one query covers 15 months for an outlet) but it captures no article-level content, no themes, no URLs, no titles.

The fields the main backfill populates on `country_activity`:

|Field|Source|Populated?|
|---|---|---|
|`today_count`|TimelineVolRaw daily count|✅|
|`baseline_mean`, `baseline_std`|30-day rolling|✅|
|`deviation_ratio`, `z_score`, `level`|From today vs baseline|✅|
|`confidence`|Days in baseline window|✅|
|`top_outlets`|Aggregated outlet contributions|✅|
|`top_themes`|—|❌ Empty `{}`|
|`articles` table|—|❌ Not populated at all|

To populate `top_themes` on historical rows, we need a **second backfill** using a different GDELT mode.

---

## CRITICAL FINDING from the first live backfill run (Apr 10, 16:34)

After the first TimelineVolRaw backfill was ~230/301 outlets deep, we reviewed the log output and identified a major coverage gap for THREE Tier 1 outlets that changes the theme source decision:

**Broken in GDELT's index:**
- `rt.com` — returned **2 articles** across 15 months (expected 100K+). GDELT cleanly returns the result in 6.9s, retries=0 — it's not a network failure, GDELT's index genuinely has almost nothing for rt.com.
- `cctv.com` — returned **0 articles** (expected 100K+).
- `cgtn.com` — returned **0 articles** (expected 50K+).
- `people.com.cn` / `en.people.cn` — hard-failed after 4-5 retries each.
- `arabic.rt.com`, `francais.rt.com`, `deutsch.rt.com` — all 0 or hard-failed.
- `arabic.cgtn.com`, `francais.cgtn.com`, `espanol.cgtn.com` — all 0.
- `irib.ir`, `iribnews.ir`, `irna.ir`, `isna.ir`, `khamenei.ir` — all 0.

**Still works:**
- `russian.rt.com` (46K), `actualidad.rt.com` (16K) — RT subdomains are indexed separately and work fine
- `news.cn` (22K), `chinadaily.com.cn` (22K), `chinanews.com.cn` (15K), `english.news.cn` (41K), `china.org.cn` (7K) — Chinese secondary outlets work
- `presstv.ir` (6,580) — Iranian English works
- All major Russian outlets except rt.com core: `ria.ru` (68K), `mk.ru` (39K), `iz.ru` (37K), `interfax.ru` (27K), `1tv.ru` (9K)
- Turkish, Serbian, Romanian, Hungarian, Brazilian, Indonesian, Japanese, Taiwanese all working with rich volumes

**Why this matters for theme source selection:**

`WordCloudEnglishThemes` uses the SAME underlying GDELT crawl index as `TimelineVolRaw`. If GDELT doesn't have articles for `rt.com`, no GDELT mode will produce themes for `rt.com`. A per-outlet theme backfill would have the exact same coverage gaps we just identified.

This means the original per-outlet-only plan leaves Russia INTERNATIONAL and Chinese DOMESTIC with thin theme data — precisely the two most important buckets for the product.

**Solution: hybrid query strategy** using BOTH per-outlet and per-country queries. Per-outlet preserves the audience split where GDELT has coverage. Per-country fills the gaps by querying `sourcecountry=XX + mode=wordcloudenglishthemes` which captures ALL articles GDELT has for a country regardless of outlet.

See "Theme source options" below for the full comparison of the three approaches.

## The right GDELT mode

### `WordCloudEnglishThemes` (recommended)

GDELT DOC 2.0 offers `WordCloudEnglishThemes` mode. It returns the top GDELT GKG (Global Knowledge Graph) themes for a given query window as a frequency map:

```
{
  "WB_2024_ANTI_CORRUPTION": 247,
  "ECON_SANCTIONS": 189,
  "NATO_EXPANSION": 156,
  "MILITARY": 142,
  ...
}
```

Key properties:

- **Returns English-LABELED theme codes** from GDELT's universal taxonomy. The "English" in the mode name refers to the label language, NOT the source article language. Theme tags are applied to articles in any of ~65 languages after GDELT's internal NLP analysis. So querying `domain_exact=rt.com` (RT English) returns English-labeled themes, and querying `domain_exact=actualidad.rt.com` (RT Spanish) ALSO returns the same English-labeled theme codes. This is exactly what we want — our theme_labels.json file is keyed by the English GKG codes.
- **Aggregated server-side.** No 250-result cap like `ArtList`. The entire query window is summarized at GDELT's side.
- **Returns frequency counts directly.** We don't extract themes from articles; GDELT does the work.
- **Works per query window.** One query = one time slice.

### Alternatives considered and rejected

|Mode|Why not|
|---|---|
|`ArtList`|Would give us article titles + URLs as a bonus, BUT the 250-result cap biases theme extraction for any high-volume window. An active month could have 5000+ articles and we'd only see 250.|
|`TimelineTone`|Returns daily tone scores only, not themes.|
|`TimelineLang`|Language distribution over time, not themes.|
|Keyword extraction from direct RSS scraping|Out of MVP scope. Takes weeks to build and maintain per-outlet.|

**Decision: `WordCloudEnglishThemes`.**

---

## Query plan

Each query covers one `(outlet, period)` tuple:

```
GET /doc2api/doc2api?
  query=domain_exact:xinhuanet.com
  &mode=wordcloudenglishthemes
  &format=json
  &startdatetime=20250101000000
  &enddatetime=20250131235959
```

Returns a JSON object of theme frequencies for that outlet over that month.

### Audience split requires per-outlet queries

GDELT's `sourcecountry` filter can't split by audience type (DOMESTIC vs INTERNATIONAL). We'd have to query per-outlet instead, then aggregate themes per `(country, audience_type, period)` in post-processing using each outlet's fixed audience classification from `outlets.json`.

This preserves the product's core pitch: "what Russia's state media tells its own citizens vs what it tells foreigners" — two separate theme lists per country per period.

### Query volume at each granularity

**Monthly (Jan 2025 – Mar 2026):**
- 301 outlets × 15 months = **4,515 queries**
- At 2.5s rate limit: ~3 hours runtime
- Produces ~4,530 `country_themes` rows after aggregation (151 countries × 2 audience types × 15 months)

**Weekly (Jan 2025 – Mar 2026):**
- 301 outlets × ~66 weeks = **19,866 queries**
- At 2.5s rate limit: ~14 hours runtime
- Produces ~19,932 `country_themes` rows

**Daily (deferred to next week):**
- 301 outlets × 464 days = 139,664 queries
- At 2.5s rate limit: ~97 hours = 4 days
- Produces ~140,128 rows

**Monthly + Weekly combined (the ask for this plan): 24,381 queries = ~17 hours total runtime.**

---

## Data storage — new `country_themes` table

A new table rather than columns on `country_activity` because the theme data has fundamentally different period cardinality than daily deviation data.

### Schema

```sql
CREATE TABLE IF NOT EXISTS country_themes (
  country        CHAR(2) NOT NULL,
  audience_type  TEXT NOT NULL CHECK (audience_type IN ('DOMESTIC', 'INTERNATIONAL', 'DIASPORA')),
  period_type    TEXT NOT NULL CHECK (period_type IN ('month', 'week', 'day')),
  period_start   DATE NOT NULL,
  period_end     DATE NOT NULL,
  themes         JSONB NOT NULL,  -- {"WB_2024_ANTI_CORRUPTION": 247, ...}
  contributing_outlets INT NOT NULL DEFAULT 0,  -- how many outlets contributed
  total_theme_mentions INT NOT NULL DEFAULT 0,  -- sum of all theme counts
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (country, audience_type, period_type, period_start)
);

CREATE INDEX IF NOT EXISTS idx_country_themes_lookup
  ON country_themes(country, audience_type, period_type, period_start DESC);
```

### Row math

Monthly rows: 151 countries × 2 audiences × 15 months = **4,530 rows**.

Weekly rows: 151 × 2 × 66 weeks = **19,932 rows**.

Combined: **~24,462 rows**. Each row is ~2KB (JSONB themes + metadata), so total storage: ~50 MB. Trivial against the 500 MB Supabase free tier cap.

### Why a new table vs columns on country_activity

- `country_activity` has one row per day × per audience type = ~280K rows at full scale after backfill
- Adding monthly and weekly theme columns to every daily row would denormalize badly and bloat the table
- `country_themes` has one row per period, which is the correct cardinality
- Keeps daily deviation queries fast (no theme JSON bloat on the country_activity hot path)
- Simpler upsert logic: theme backfill writes to country_themes only, never touches country_activity

---

## New files

### Backend

1. **`pipeline/src/gdelt_theme_client.py`** — wraps `WordCloudEnglishThemes` mode. Similar shape to `gdelt_timeline_client.py`: rate limit, exponential backoff, 5-retry cap, HTTP timeout, empty-response handling. Function signature:
   ```python
   def query_domain_themes(
       domain: str,
       start_date: date,
       end_date: date,
       *,
       rate_limit_seconds: float = 2.5,
       max_retries: int = 5,
       http_timeout: float = 30.0,
   ) -> ThemeResult
   ```
   Returns `ThemeResult` with fields: `domain`, `start_date`, `end_date`, `themes: dict[str, int]`, `total_mentions`, `duration_seconds`, `retries`.

2. **`pipeline/src/theme_backfill.py`** — core aggregation logic. Takes outlets + period definitions (list of (period_type, period_start, period_end) tuples), runs queries, aggregates per (country, audience, period), returns `country_themes` rows ready for bulk upsert.

3. **`pipeline/scripts/run_theme_backfill.py`** — CLI entry point. Flags:
   - `--granularity` = `monthly` | `weekly` | `both`
   - `--start-date`, `--end-date`
   - `--output-json PATH`
   - `--resume-from DOMAIN` (for crashed-run recovery)
   - `--outlets-file PATH`
   - `--dry-run`, `--verbose`, `--force`

4. **`pipeline/scripts/import_theme_backfill.py`** — validation + Supabase upsert. Validation passes:
   - Schema shape (every row has the required keys)
   - Value ranges (theme counts non-negative, period_start ≤ period_end)
   - Date coverage (no massive gaps)
   - FVEY exclusion (hard rule)
   - Volume ceiling (<50K rows as sanity check)

### Database

5. **`shared/schema.sql`** — add `country_themes` table, bump `REQUIRED_SCHEMA_VERSION` from 2 to 3. The pipeline's pre-flight check (`db.get_schema_version()`) will refuse to run against an unmigrated DB.

### Frontend

6. **`src/components/Country/ThemePicker.tsx`** — the UI component. Layout:
   ```
   ┌ Themes in [Country Name] ────────────────┐
   │                                           │
   │  [Monthly] [Weekly]      [◄ Apr 2025 ►]  │
   │                                           │
   │  DOMESTIC                   INTERNATIONAL │
   │  ───────                    ───────       │
   │  [Anti-Corruption]          [NATO Expansion] │
   │    247                       189          │
   │  [Economic Sanctions]       [Russia Sanctions]│
   │    189                       156          │
   │  [CCP]                      [Ukraine War] │
   │    142                       134          │
   │  ...                         ...          │
   └───────────────────────────────────────────┘
   ```
   Props:
   - `countryIso2: string`
   - `initialPeriodType?: 'month' | 'week'` (default `'month'`)
   - Defaults to the most recent complete period on mount.

7. **`src/lib/data.ts`** — new function:
   ```typescript
   getCountryThemes(
     iso2: string,
     periodType: 'month' | 'week',
     periodStart: string,  // YYYY-MM-DD
   ): Promise<{ domestic: ThemeCount[]; international: ThemeCount[] }>
   ```
   Queries Supabase `country_themes` by (country, period_type, period_start) and groups by audience_type.

8. **`src/app/country/[code]/page.tsx`** — wire `<ThemePicker />` into the existing page layout. Position it between the audience split section and the headline feed.

### Tests

9. **`pipeline/tests/test_gdelt_theme_client.py`** — mock GDELT responses, assert parser handles empty/missing/normal cases
10. **`pipeline/tests/test_theme_backfill.py`** — aggregation logic with synthetic outlets + fake theme client
11. **`pipeline/tests/test_import_theme_backfill.py`** — validation passes + upsert behavior

---

## Theme label handling

The theme codes returned by GDELT (`WB_2024_ANTI_CORRUPTION`, `ECON_SANCTIONS`, etc.) are raw machine codes. We already have `pipeline/data/theme_labels.json` (137 entries after C12 expansion) that maps codes to human-readable labels + descriptions.

Frontend display path:
1. Frontend receives theme code + count from the data adapter
2. Looks up the code in `theme_labels.json` (bundled at build time)
3. Displays the human-readable label
4. If no label exists (new theme GDELT returns that we haven't catalogued), displays the raw code as a fallback

The theme_labels.json file needs expansion beyond 137 entries to cover whatever GDELT actually returns. We'll discover this empirically once the theme backfill produces real data — I'll write a script `pipeline/scripts/audit_theme_coverage.py` that reads the backfill output, finds every theme code that appears, and flags missing labels for manual expansion.

---

## Execution sequence

### Option A — monthly tonight, weekly tomorrow (RECOMMENDED)

|Step|When|Duration|
|---|---|---|
|Main backfill finishes|Tonight, ~16:50|~35 min|
|Main backfill import|Tonight, ~17:00|~5 min|
|Globe goes live with real baselines (no themes yet)|Tonight, ~17:00|—|
|Claude builds theme backfill scripts + tests in parallel|Tonight, 17:00–18:30|~90 min|
|Monthly theme backfill run|Tonight, 18:30–21:30|~3 hours|
|Monthly theme import + schema migration|Tonight, 21:30|~10 min|
|ThemePicker UI component built|Tonight, 21:40–22:40|~60 min|
|Monthly themes LIVE on country pages|Tonight, 22:45|—|
|Weekly theme backfill run|Friday night → Saturday morning|~14 hours|
|Weekly theme import|Saturday morning, ~08:00|~5 min|
|UI toggle enables weekly view|Saturday morning, ~08:10|—|
|Daily granularity|Next week|~4 days runtime|

**Total user time tonight:** ~30 min of attention spread across the sessions. Monthly feature live by tonight. Weekly live by Saturday morning.

### Option B — monthly + weekly in one overnight run

|Step|When|Duration|
|---|---|---|
|Main backfill + import|Tonight, ~16:50–17:00|~40 min|
|Claude builds scripts|Tonight, 17:00–18:30|~90 min|
|Combined monthly+weekly backfill|Tonight 18:30 → Saturday morning|~17 hours|
|Import + UI build|Saturday morning|~2 hours|
|Monthly + weekly LIVE|Saturday afternoon|—|

**Problem with Option B:** your laptop has to stay on (lid open) and awake overnight, with power, with stable internet, for 17 hours continuously. Any sleep / wifi drop / power blip mid-run means we lose progress. Option A splits the risk into two shorter runs.

### Option C — weekly only (no separate monthly)

Weekly themes can be aggregated into monthly themes in the frontend by summing 4 consecutive weeks. This means one backfill run (14 hours) instead of two (3 + 14), trading 3 hours of runtime for slightly worse monthly quality (weekly buckets don't align perfectly with calendar months).

**Decision:** Option A (monthly tonight, weekly tomorrow) unless user explicitly wants Option B or Option C.

---

## Integration with the Render cron (future)

Once the monthly theme backfill is live, we need to KEEP it updated as new months roll in. Two approaches:

**A — periodic re-run.** On the first of each month, manually (or via a scheduled task) run the theme backfill for just the previous month. Low operational cost, ~20 minutes per month.

**B — integrate with Render cron.** The live hourly pipeline already uses ArtList mode which returns per-article themes. We could accumulate daily theme rollups as the cron runs, then aggregate daily → weekly → monthly as part of the pipeline. More complex but fully automated.

**MVP: Option A.** Approach B goes on the "future enhancements" list.

---

## Open questions (need user decision before Claude starts building)

### 1. Theme source strategy (UPDATED after Tier 1 coverage finding)

Three real options, each documented in the "CRITICAL FINDING" section above:

**Option A — Per-outlet WordCloudEnglishThemes only** (the original plan)
- Query: `domain_exact=<outlet> + mode=wordcloudenglishthemes + period`
- Pro: preserves DOMESTIC vs INTERNATIONAL audience split cleanly
- Con: rt.com, cctv.com, cgtn.com, and other broken-in-GDELT Tier 1 outlets contribute zero themes. Russia INTERNATIONAL and China DOMESTIC theme buckets will be thin.
- Query count (monthly + weekly): 301 outlets × (15 + 66) = ~24,381 queries
- Runtime: ~17 hours at 2.5s rate limit

**Option B — Per-country WordCloudEnglishThemes only**
- Query: `sourcecountry=<FIPS> + mode=wordcloudenglishthemes + period`
- Pro: captures every article GDELT has for a country, including outlets we don't monitor. No coverage gap for Tier 1 outlets.
- Con: no audience split — themes are aggregated across DOMESTIC and INTERNATIONAL outlets together. We lose the product's core pitch.
- Query count: 151 countries × (15 + 66) = ~12,231 queries
- Runtime: ~8.5 hours at 2.5s rate limit (half of Option A)

**Option C — Hybrid (RECOMMENDED)**
- Primary: Option A per-outlet queries. Aggregate results by (country, audience_type, period).
- Fallback: After the primary aggregation, identify (country, audience_type, period) buckets where total theme mentions < 100 (or similar threshold). For those thin buckets, run an Option B query (by sourcecountry) as a supplement. Mark those rows with an `is_fallback=true` flag so the frontend can label them.
- Pro: keeps audience split where GDELT has coverage. Rescues broken Tier 1 buckets with country-level data.
- Pro: honest — the UI labels fallback rows so users know when the audience split isn't available.
- Con: two query passes. Slightly more engineering.
- Query count: ~24,381 primary + maybe 1,000-2,000 fallback = **~25,500 queries total**
- Runtime: ~17.5 hours (only 30 minutes more than Option A)

**Recommendation: Option C (hybrid).** The small runtime cost buys us coverage for the most important Tier 1 buckets that would otherwise be empty. Frontend labeling is a one-line change: when `is_fallback=true`, show "Country-wide themes — audience split unavailable due to GDELT coverage gap."

**User call:** ✅ A, B, or C.

### 2. Execution sequencing

**Option A (recommended):** monthly theme backfill tonight (3 hours), weekly theme backfill overnight into Saturday morning (14 hours). Monthly feature live tonight, weekly live Saturday morning.

**Option B:** both monthly and weekly in one 17-hour overnight run. Requires laptop to stay awake and online for 17 hours continuously.

**Option C:** weekly only, aggregate to monthly in the frontend. Single 14-hour run, one less backfill.

**User call:** ✅ A, B, or C.

### 3. UI details

Current plan is a date-picker card with:
- Granularity toggle (Monthly / Weekly)
- Previous/next arrow buttons to step through periods
- Defaults to most recent complete period
- Two columns: DOMESTIC themes | INTERNATIONAL themes
- Theme chips with human-readable labels + counts

**Alternatives worth considering:**
- Calendar grid view (click any month in a mini calendar)
- Timeline slider (drag a horizontal slider across the 15 months)
- List view (all months on the page, scrollable)
- Search / filter by theme ("show me every month where Russia's state media talked about sanctions")

**User call:** stick with the arrow-button picker (simplest), or go with a different affordance.

### 4. Anything else

- Should we also store the number of contributing outlets + total theme mentions per period for transparency ("this month's top themes based on 4,237 articles across 12 outlets")? **Recommended: yes, already in the schema.**
- Should theme chips be clickable to filter the headline feed to that theme? **Future enhancement, not MVP.**
- Should there be a "trending themes" callout that highlights themes that appeared this month but not last month? **Future enhancement.**
- Should we offer CSV export of a country's theme history? **Post-launch.**

---

## Risks and mitigations

|Risk|Likelihood|Mitigation|
|---|---|---|
|GDELT rate-limits kill the theme backfill|MEDIUM|5-retry exponential backoff; resume-from-outlet recovery; incremental write to JSON|
|`WordCloudEnglishThemes` mode not supported by `gdeltdoc 1.12.0`|LOW|Verify via a 1-outlet smoke test before the full run|
|Theme codes returned don't match `theme_labels.json` coverage|HIGH|Audit script flags missing labels post-run; expand theme_labels.json with new codes; UI falls back to raw code display|
|Weekly backfill doesn't finish overnight (17 hr > sleep period)|MEDIUM|Split into chunks; use `--resume-from` to continue across sessions|
|Schema version mismatch between pipeline and Supabase|LOW|Bump `REQUIRED_SCHEMA_VERSION` in pipeline/src/db.py; pre-flight check fails fast|
|UI picker is confusing for users|LOW|Start with simplest picker; iterate based on feedback|

---

## Deferred (explicitly next week or later)

- **Daily granularity** (~4 days runtime, ~140K queries). Don's ask: "We can look at daily next week."
- **Trend detection** (themes rising/falling over time)
- **Theme → headline drill-down** (click a theme chip, see the articles that mention it)
- **Cross-country theme comparison** ("what themes is Russia pushing that China isn't?")
- **Non-English theme codes** (if GDELT supports them — need research)
- **Custom narrative theme extraction** beyond GDELT's GKG taxonomy (this was always a Phase 8+ item per the original SalientSignal-Way-Ahead.md plan)
- **Automated theme backfill refresh** as new months roll in (Render cron integration vs manual monthly run)

---

## File inventory summary

### New files to create (11)

Pipeline:
- `pipeline/src/gdelt_theme_client.py`
- `pipeline/src/theme_backfill.py`
- `pipeline/scripts/run_theme_backfill.py`
- `pipeline/scripts/import_theme_backfill.py`
- `pipeline/scripts/audit_theme_coverage.py`
- `pipeline/tests/test_gdelt_theme_client.py`
- `pipeline/tests/test_theme_backfill.py`
- `pipeline/tests/test_import_theme_backfill.py`

Frontend:
- `src/components/Country/ThemePicker.tsx`
- `src/components/Country/ThemeChipRow.tsx` (subcomponent)

Docs:
- `docs/THEME_BACKFILL.md` (operational runbook for future theme backfill runs)

### Existing files to modify (5)

- `shared/schema.sql` — add `country_themes` table, bump schema_version to 3
- `pipeline/src/db.py` — add `upsert_country_themes_batch()` method + `REQUIRED_SCHEMA_VERSION = 3`
- `pipeline/data/theme_labels.json` — expand based on audit of actual GDELT output (post-run)
- `src/lib/data.ts` — add `getCountryThemes()` function
- `src/app/country/[code]/page.tsx` — render `<ThemePicker />` in the page layout

---

## Appendix: example `country_themes` row

```json
{
  "country": "RU",
  "audience_type": "INTERNATIONAL",
  "period_type": "month",
  "period_start": "2025-02-01",
  "period_end": "2025-02-28",
  "themes": {
    "ECON_SANCTIONS": 487,
    "NATO_EXPANSION": 342,
    "WB_2012_CONFLICT_AND_VIOLENCE": 298,
    "MILITARY": 276,
    "WB_2170_PEACE_AND_SECURITY": 245,
    "TAX_ETHNICITY_UKRAINIAN": 198,
    "USPEC_POLICY1": 187,
    "ELECTION": 156,
    "NUCLEAR_WEAPONS": 134,
    "DIPLOMATIC_CRISIS": 122
  },
  "contributing_outlets": 8,
  "total_theme_mentions": 3412,
  "created_at": "2026-04-10T22:15:00Z",
  "updated_at": "2026-04-10T22:15:00Z"
}
```

And the frontend rendering that row for the user (after theme_labels.json lookup):

```
DOMESTIC (Feb 2025, 8 outlets, 3,412 mentions)
─────────────────────────────────────────────
Economic Sanctions      487
NATO Expansion          342
Conflict & Violence     298
Military                276
Peace & Security        245
Ukrainian Ethnicity     198
U.S. Policy             187
Elections               156
Nuclear Weapons         134
Diplomatic Crisis       122
```

---

## Ready-state checklist (before kicking off Phase 2)

- [ ] Main backfill (TimelineVolRaw) completes successfully
- [ ] Main backfill JSON validates via `import_backfill.py --dry-run`
- [ ] Main backfill imported to Supabase (`country_activity` has ~130K rows)
- [ ] Globe updates at salientsignal.com show real deviation colors (not cold-start)
- [ ] User confirms they want Option A/B/C execution sequencing
- [ ] User confirms `WordCloudEnglishThemes` as theme source
- [ ] Claude builds theme backfill scripts + runs tests locally
- [ ] Smoke test: 1 outlet × 1 month via real GDELT to confirm the mode works in `gdeltdoc 1.12.0`
- [ ] Schema migration SQL ready (add `country_themes`, bump version)
- [ ] Theme backfill command ready to paste into a new terminal tab (same approach as main backfill — single-line command, no multi-line zsh paste)

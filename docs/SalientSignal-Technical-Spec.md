---
aliases:
  - SalientSignal Tech Spec
  - Technical Specification
tags:
  - apex
  - business
  - app
  - engineering
created: 2026-04-09
---

# SalientSignal — Technical Specification

> **Verified numbers, exact API calls, complete daily/weekly/monthly operations breakdown.**

---

## Verified Platform Limits

### GDELT DOC 2.0 API (Primary Data Source)

| Parameter | Verified Value | Source |
|-----------|---------------|--------|
| Max results per query | **250 articles** (MAXRECORDS parameter) | GDELT DOC 2.0 documentation |
| Default results | 75 | GDELT DOC 2.0 documentation |
| Update frequency | Every **15 minutes** | GDELT project page |
| Search window | Rolling **3 months** from present | GDELT DOC 2.0 documentation |
| Minimum timespan | 15 minutes | GDELT DOC 2.0 documentation |
| Rate limits | **Not published.** Dynamic, based on system load. 429 errors possible during peak events. | GDELT blog |
| Authentication | **None required** | GDELT DOC 2.0 documentation |
| Output formats | HTML, CSV, JSON, JSONP, RSS, JSONFeed | GDELT DOC 2.0 documentation |
| Languages monitored | **65 languages** machine-translated in real-time (98.4% of non-English volume) | GDELT project page |
| Daily article volume | **500,000 - 1,000,000 articles/day** across all sources globally | GDELT datasets documentation (2016 figure, likely higher now) |
| Cost | **$0** | Free, open access |

**Key query capabilities:**
- `domainis:rt.com` — filter to exact domain
- `sourcecountry:ru` — filter by country (FIPS code)
- `sourcelang:spanish` — filter by source language
- `theme:TERROR` — filter by GDELT theme taxonomy
- `tone<-5` or `tone>5` — filter by sentiment
- Timeline modes: `TimelineVol`, `TimelineVolRaw`, `TimelineTone`, `TimelineLang`, `TimelineSourceCountry`

**Limitation:** 250 articles per query means you need multiple queries to cover all outlets for a country. A country like Russia with 10+ outlets requires batched queries.

### Vercel Free Tier (Hobby Plan)

| Parameter | Verified Value |
|-----------|---------------|
| Bandwidth | **100 GB/month** (~100K visitors) |
| Serverless function invocations | **150,000/month** |
| Function execution hours | **1,000 hours/month** |
| Build minutes | **6,000/month** |
| Projects | Unlimited |
| Cron jobs (free tier) | **1 cron, daily only** |
| Cron jobs (Pro $20/mo) | Unlimited, down to 1-minute intervals |
| Overage: bandwidth | $20 per 100 GB |
| Overage: functions | $4 per 100K invocations |

**Critical constraint:** Free tier only allows 1 daily cron job. The pipeline needs hourly (or more frequent) updates. **Workaround:** Use cron-job.org (free, 1-minute granularity, unlimited jobs) to hit Vercel API routes on schedule.

### Neon PostgreSQL Free Tier

| Parameter | Verified Value |
|-----------|---------------|
| Storage | **0.5 GB per project** (5 GB aggregate across projects) |
| Compute | **100 CU-hours/month per project** |
| Projects | Up to 100 |
| Auto-suspend | Scales to zero when idle |
| Point-in-time restore | Last 6 hours |
| Cost | **$0** |

**Constraint:** 0.5 GB per project is tight for a growing article archive. At ~2 KB per article record (metadata + debrief text, not full article body), 0.5 GB holds ~250,000 records. That's roughly 8 months of data at 1,000 articles/day. Full article text storage would need Supabase or a paid Neon tier.

### Supabase Free Tier (Alternative)

| Parameter | Verified Value |
|-----------|---------------|
| Database storage | **500 MB** |
| File storage | **1 GB** |
| API requests | **Unlimited** |
| MAUs (auth) | **50,000** |
| Edge function invocations | **500,000/month** |
| Database egress | **5 GB/month** |
| Projects | **2 active** |
| Inactivity pause | **After 1 week** |

**Better for auth** (built-in email verification for .mil accounts). Same storage constraint as Neon. Unlimited API requests is valuable.

### Globe.gl

| Parameter | Value |
|-----------|-------|
| GeoJSON support | Polygon and MultiPolygon (Natural Earth compatible) |
| Recommended data | `ne_110m_admin_0_countries.geojson` (lightweight, all countries) |
| Higher detail | `ne_50m` and `ne_10m` available for zoom |
| Rendering | WebGL via Three.js |
| React component | `react-globe.gl` |
| Click handlers | `onPolygonClick(polygon, event, coords)` |
| Arc support | Built-in arc layer for coordination visualization |
| Cost | **$0** (MIT license) |
| Mobile | Works but polygon resolution affects performance. Use 110m for mobile. |

---

## Complete Daily Pipeline

### What Runs Every Hour (24 times/day)

**Step 1: GDELT Query Batch**

Query GDELT DOC 2.0 API for each monitored country's state media domains. With 151 countries and ~606 outlets, queries are batched by country.

```
Per query: 1 GDELT API call
Max results: 250 articles
Timespan: last 1 hour (to catch new articles since last run)

Estimated queries per hourly run:
- Tier 1 countries (Russia, China, Iran, DPRK): 4 countries x 3-5 queries each = ~16 queries
  (Multiple queries needed because RT alone has rt.com, russian.rt.com, arabic.rt.com, etc.)
- Tier 2 countries (Turkey, Gulf, Venezuela, etc.): 12 countries x 1-2 queries = ~20 queries
- Tier 3 countries (all others): ~135 countries x 1 query = ~135 queries
  (Most small countries produce <250 articles/hour, so 1 query suffices)

Total GDELT queries per hourly run: ~171 queries
Total GDELT queries per day: 171 x 24 = ~4,104 queries/day
```

**What each query returns (JSON format):**
- Article URL
- Article title
- Source domain
- Source country (FIPS code)
- Source language
- Publication date
- Tone score (sentiment, -10 to +10)
- Social sharing image URL

**What GDELT does NOT return:**
- Full article text (need to fetch separately)
- Theme tags (available via separate GKG/Context API)
- Entity extraction (available via separate GKG)

**Step 2: Article Text Extraction (for top articles only)**

Full article text is needed for the SCAME analysis. But extracting ALL articles is wasteful — most are routine. Extract text for:
- All articles from Tier 1 countries (Russia, China, Iran, DPRK)
- Articles with extreme tone scores (>5 or <-5) from any country
- Articles from countries showing baseline deviation (spike or silence)
- Articles on trending themes

```
Estimated articles needing full text extraction per hour:
- Tier 1 countries: ~200-500 articles/hour
- Anomaly articles: ~50-100/hour
- Total: ~300-600 articles/hour needing Trafilatura extraction

Trafilatura extraction: ~0.5-2 seconds per article
Total time: ~150-1,200 seconds = 2.5-20 minutes per hourly batch
Cost: $0 (Trafilatura is free, runs server-side)
```

**Step 3: Theme Classification (GDELT GKG)**

GDELT's Global Knowledge Graph already classifies articles by theme. Query the GKG for theme data on the articles collected in Step 1.

```
Separate GKG query per country batch
Same rate limit concerns as DOC API
Theme taxonomy: GDELT CAMEO codes + custom themes
Cost: $0
```

**Step 4: Baseline Calculation**

For each country, compare today's article count to its 30-day rolling average.

```
Simple database query: 
SELECT country, COUNT(*) as today, AVG(daily_count) as baseline 
FROM articles 
WHERE date = today 
GROUP BY country

Runs once per hour after ingestion
Cost: $0 (database compute)
```

**Step 5: Store Results**

Write to PostgreSQL/Supabase:
- Article metadata (URL, title, source, country, language, tone, timestamp)
- Full text (for extracted articles only)
- Theme tags
- Baseline deviation scores

```
Records per day: ~5,000-15,000 new article records
Storage per record: ~1-3 KB (metadata) or ~5-10 KB (with full text)
Daily storage growth: ~15-50 MB (metadata only) or ~50-150 MB (with text)
Monthly storage growth: ~0.5-1.5 GB (metadata) or ~1.5-4.5 GB (with text)
```

> [!warning] Storage Constraint
> Free tier databases (Neon 0.5 GB, Supabase 500 MB) will fill in 1-3 months with metadata only, or 1 month with full text. **The free MVP must either purge old data or only store metadata + current day's articles in the database, with historical data in flat files or a separate archive.**

### What Runs Every 6 Hours (4 times/day)

**Step 6: Cross-Language Comparison**

For events covered by multiple language desks from the same country, compare framing:

```
Query: Find events where RT English, RT Arabic, RT Spanish all published
For each match: extract headlines + key framing words
Flag divergences for potential SCAME analysis

This is a database query + text comparison
No external API calls needed for the free tier
Cost: $0

For paid tier: send matched pairs to Claude API for debrief paragraph
Claude Haiku call: ~500-1,000 input tokens + ~200-300 output tokens per comparison
Estimated comparisons per 6-hour batch: ~20-50
Claude Haiku cost per comparison: ~$0.0005-0.001
Daily cost (4 batches): ~$0.04-0.20
```

**Step 7: Theme Aggregation**

Roll up theme counts per country for the current period:

```
Database aggregation query
No external API needed
Output: theme_name, country, count_today, count_30day_avg, deviation_ratio
Cost: $0
```

### What Runs Once Daily (0500 local)

**Step 8: Morning Brief Generation (PAID TIER ONLY)**

For the paid tier, Claude generates debrief paragraphs for the top stories.

```
Top stories to brief: ~10-20 per day (global morning brief)
Per story: ~1,000-2,000 input tokens (article summaries + metadata) + ~200-400 output tokens (debrief paragraph)

Claude Haiku 4.5:
- Input: $0.80/M tokens
- Output: $4.00/M tokens

Per story: (1,500 x $0.80/1M) + (300 x $4.00/1M) = $0.0012 + $0.0012 = $0.0024
20 stories/day: $0.048/day = ~$1.44/month

Claude Sonnet 4.6 (for deeper analysis):
- Input: $3.00/M tokens  
- Output: $15.00/M tokens

Per story: (1,500 x $3.00/1M) + (300 x $15.00/1M) = $0.0045 + $0.0045 = $0.009
20 stories/day: $0.18/day = ~$5.40/month
```

**Step 9: Country Briefs (PAID TIER ONLY)**

Generate country-specific briefs for active countries:

```
Countries with notable activity: ~20-40/day
Per country brief: ~$0.0024 (Haiku) or ~$0.009 (Sonnet)
Daily: $0.048-0.36
Monthly: $1.44-$10.80
```

**Step 10: Daily Archive Snapshot**

Snapshot today's data for the historical archive:

```
Aggregate all article metadata, theme counts, baseline deviations, 
cross-language comparisons into a daily summary record.

Write to: daily_snapshots table
Fields: date, country_activity_json, theme_counts_json, 
        contradictions_json, top_stories_json, baseline_deviations_json

One record per day: ~10-50 KB
Monthly: ~300 KB - 1.5 MB
Cost: $0
```

### What Runs Weekly (Sunday 0600)

**Step 11: Weekly Digest Generation**

```
Aggregate 7 daily snapshots into weekly rollup:
- Top 10 themes of the week (with delta vs. prior week)
- Countries with biggest baseline deviations
- Notable contradictions detected
- New gray accounts identified (paid tier only)
- "Silence signals" — countries that went unusually quiet

Database queries only for free tier.
Claude generation for paid tier: ~$0.01-0.05 per weekly digest
Monthly (4 weeks): $0.04-0.20
```

**Step 12: Baseline Recalibration**

```
Recalculate 30-day rolling averages for all countries.
Database query across last 30 daily snapshots.
Update baseline_averages table.
Cost: $0
```

### What Runs Monthly (1st of month, 0600)

**Step 13: Monthly Report Generation**

```
Aggregate 4-5 weekly digests into monthly report:
- Theme rankings with month-over-month change
- Country activity heatmap data
- Narrative lifecycle charts (new themes, peaked themes, faded themes)
- Quarterly trend lines (after 3+ months of data)

Database queries for free tier.
Claude generation for paid tier: ~$0.02-0.10
```

**Step 14: Storage Maintenance**

```
Free tier storage management:
- Archive old article metadata to flat JSON files (Vercel Blob or external)
- Keep only last 30 days of full article records in database
- Daily snapshots stay in DB permanently (tiny footprint)

Or: upgrade to Neon Pro ($19/mo) or Supabase Pro ($25/mo) for 8 GB+ storage
```

---

## Complete Cost Breakdown

### Free Tier MVP ($0/month)

| Component | Service | Monthly Cost |
|-----------|---------|-------------|
| Data ingestion | GDELT DOC 2.0 API | $0 |
| Theme classification | GDELT GKG | $0 |
| Article extraction | Trafilatura (Python) | $0 |
| Globe visualization | Globe.gl + react-globe.gl | $0 |
| GeoJSON data | Natural Earth (public domain) | $0 |
| Web hosting | Vercel Hobby | $0 |
| Database | Supabase Free (500 MB, unlimited API) | $0 |
| Auth (.mil verification) | Supabase Auth (50K MAUs free) | $0 |
| Cron scheduling | cron-job.org (free, 1-min granularity) | $0 |
| **TOTAL** | | **$0/month** |

**What free users get:**
- Interactive globe with baseline deviation coloring (recalculated hourly)
- Today's state media headlines by country and outlet (GDELT data)
- Theme tracking (GDELT GKG themes, aggregated)
- Cross-language headline comparison (raw data, no AI analysis)
- Country pages with current-day data

**What free users DON'T get:**
- AI-generated debrief paragraphs (requires Claude API)
- Gray source detection (requires Grok API)
- Historical archive beyond today
- Trend explorer
- Weekly/monthly digests
- Push alerts
- Search

### Paid Tier Operations ($10/month subscription)

| Component | Service | Monthly Cost |
|-----------|---------|-------------|
| Everything in free tier | (same) | $0 |
| Morning brief generation | Claude Haiku (20 stories/day) | $1.50 |
| Country briefs | Claude Haiku (30 countries/day) | $2.20 |
| Cross-audience analysis | Claude Haiku (50 comparisons/day) | $3.00 |
| Weekly digests | Claude Haiku (4/month) | $0.20 |
| Monthly report | Claude Sonnet (1/month) | $0.10 |
| Deep dives | Claude Sonnet (10/month) | $1.00 |
| Database (scaled) | Supabase Pro or Neon Launch | $25 |
| Cron jobs (hourly) | Vercel Pro or cron-job.org free | $0-20 |
| **TOTAL FIXED COST** | | **$33-53/month** |

**Break-even:** 4-6 paid subscribers at $10/month covers all fixed costs.

> [!note] Grok API costs are NOT included in MVP
> Grok integration (gray source detection, X/Twitter monitoring) is Phase 2. MVP launches with GDELT + Claude only. Grok adds ~$50-150/month when implemented.

### Scale Phase (500+ subscribers)

| Component | Monthly Cost |
|-----------|-------------|
| Free tier infrastructure | $0 |
| Claude API (increased volume) | $15-30 |
| Grok API (gray source detection) | $50-150 |
| Google Cloud Translation (batch) | $20-50 |
| Database (Supabase Pro or Neon Scale) | $25-75 |
| Vercel Pro | $20 |
| **TOTAL** | **$130-325/month** |
| **Revenue (500 paid subs)** | **$5,000/month** |

---

## API Call Budget Per Day

### Free Tier

| Operation | Frequency | API Calls | Daily Total |
|-----------|-----------|-----------|-------------|
| GDELT DOC queries (all countries) | Hourly | 171/batch | 4,104 |
| GDELT GKG queries (themes) | Hourly | ~50/batch | 1,200 |
| Trafilatura extractions | Hourly | ~300-600/batch | 7,200-14,400 |
| Supabase writes | Hourly | ~500-1,500/batch | 12,000-36,000 |
| Supabase reads (user requests) | On demand | ~10-50/user/day | Scales with users |
| Vercel serverless invocations | Hourly + on demand | ~200-500/batch | 5,000-12,000 |
| **Vercel monthly invocations** | | | **~150K-360K** |

> [!warning] Vercel Free Tier Limit
> 150,000 serverless invocations/month. The pipeline alone uses ~150K-360K. **Vercel Pro ($20/mo) or an alternative host is likely needed even for the free tier pipeline.** Alternative: run the pipeline on a $5/mo VPS (Railway, Fly.io, Render) and use Vercel only for the frontend.

### Revised Free Tier Architecture

```
Pipeline (backend): Railway free tier ($0) or Render free tier ($0)
  - Python cron jobs running GDELT queries, Trafilatura extraction, DB writes
  - No Vercel function invocations consumed

Frontend (web): Vercel Hobby ($0)
  - Next.js serves the globe, country pages, briefs
  - Reads from Supabase (unlimited API reads)
  - Serverless invocations only for page renders + API routes

This separates pipeline compute from frontend serving
and keeps both within free tier limits.
```

| Component | Service | Cost |
|-----------|---------|------|
| Pipeline backend | Railway free / Render free / Fly.io free | $0 |
| Frontend | Vercel Hobby | $0 |
| Database | Supabase Free | $0 |
| Cron trigger | cron-job.org | $0 |
| **TOTAL** | | **$0** |

---

## Storage Growth Projections

### Article Metadata Only (URL, title, source, country, language, tone, date)

| Timeframe | Records | Storage |
|-----------|---------|---------|
| 1 day | ~5,000-15,000 | ~5-15 MB |
| 1 week | ~35,000-105,000 | ~35-105 MB |
| 1 month | ~150,000-450,000 | ~150-450 MB |
| 3 months | ~450,000-1,350,000 | ~450 MB - 1.35 GB |
| 1 year | ~1.8M-5.4M | ~1.8 - 5.4 GB |

### Daily Snapshots (aggregated summaries)

| Timeframe | Records | Storage |
|-----------|---------|---------|
| 1 month | 30 | ~1 MB |
| 1 year | 365 | ~12 MB |
| 5 years | 1,825 | ~60 MB |

### Free Tier Strategy

**Month 1-2:** Store everything in Supabase (500 MB). Fits comfortably.

**Month 3+:** Article metadata approaches 500 MB limit. Options:
1. **Purge articles older than 30 days from DB, keep daily snapshots.** Free users only see today anyway. Paid users query snapshots (tiny) + last 30 days of full data.
2. **Move to Supabase Pro ($25/mo)** when first paid subscribers cover the cost.
3. **Use Vercel Blob Storage** (free tier: 1 GB) for archived article JSON.

---

## Globe Technical Implementation

### Data Flow to Globe

```
Supabase → API route → Globe.gl props

Every hour:
1. Pipeline updates country_activity table in Supabase
2. Frontend API route queries: SELECT country_code, article_count, baseline_avg, 
   deviation_ratio, top_themes FROM country_activity WHERE date = today
3. Globe.gl renders polygons colored by deviation_ratio
4. Arc data from narrative_coordination table renders as arcs
```

### GeoJSON

- `ne_110m_admin_0_countries.geojson` — 240 KB, all countries, fast load
- Each polygon has ISO_A2 country code for joining with article data
- Load once on page load, update colors reactively

### Performance Budget

| Metric | Target |
|--------|--------|
| GeoJSON load | <500ms |
| Initial globe render | <1s |
| Country click response | <200ms |
| Hourly color update | <100ms (just prop change, no reload) |
| Mobile (iPhone 12+) | 30fps minimum |
| Bundle size (globe component) | <500 KB gzipped |

---

## Daily Operations Timeline

```
EVERY HOUR (via cron-job.org → Railway/Render backend):
├── :00 — GDELT query batch starts (171 queries, ~2-3 min)
├── :03 — Article metadata stored in Supabase
├── :03 — Trafilatura extraction for top articles (~5-10 min)
├── :13 — Full text stored for extracted articles
├── :13 — GKG theme query batch (~1-2 min)
├── :15 — Theme tags stored
├── :15 — Baseline deviation recalculated per country
├── :16 — Country activity table updated (drives globe colors)
└── :16 — Cycle complete. Globe reflects latest data.

DAILY at 0500:
├── Morning brief generated (paid: Claude API, free: top headlines list)
├── Country briefs generated for top 30 active countries (paid only)
├── Cross-language comparison run for all multi-desk events
├── Daily snapshot written to archive table
└── Push alerts sent for narrative surges (paid only)

WEEKLY on Sunday 0600:
├── Weekly digest generated from 7 daily snapshots
├── 30-day baseline recalibrated for all countries
├── New theme emergence detection (themes that didn't exist last week)
└── "Silence report" — countries that dropped below 0.5x baseline

MONTHLY on 1st at 0600:
├── Monthly report generated from 4-5 weekly digests
├── Theme lifecycle analysis (new, peaked, faded, resurgent)
├── Storage maintenance (archive/purge old article records if needed)
└── Quarterly trend lines updated (after month 3+)
```

---

## What The User Sees

### Free User — Daily Experience

1. Opens site → Globe loads with today's country colors (baseline deviation)
2. Sees which countries are hot (spiking), cold (quiet), or neutral
3. Sees arc lines connecting countries pushing similar themes
4. Taps a country → sees today's headlines from that country's state media, organized by outlet and language
5. Sees GDELT theme tags for that country (what topics state media is covering)
6. Sees headline comparison across language desks (RT English headline vs. RT Arabic headline)
7. Cannot access: yesterday's data, trend charts, AI debrief paragraphs, search, alerts

### Paid User — Daily Experience

1. Same globe, same interactivity
2. Taps a country → sees AI-generated debrief paragraphs analyzing today's coverage
3. Opens morning brief → reads analytical summaries of top global stories
4. Opens trend explorer → sees theme frequency over any time range
5. Uses time slider → watches globe animate through last 30 days
6. Receives push alert: "Narrative surge: Russian media Spanish-language coverage of NATO up 340% vs. baseline"
7. Searches archive: "What did Chinese media say about Taiwan in February?"
8. Exports weekly digest as PDF for their team

### .mil User — Same as Paid, $0

---

## Verified Numbers Summary

| Claim | Verified? | Actual Number |
|-------|-----------|---------------|
| GDELT is free | YES | $0, no auth required |
| GDELT updates every 15 min | YES | Documented |
| GDELT covers 100+ languages | YES | 65 machine-translated (98.4% of non-English) + English = 66+ |
| GDELT covers every country | YES | Documented as "nearly every corner of every country" |
| GDELT max 250 results/query | YES | MAXRECORDS=250 |
| Vercel free: 100 GB bandwidth | YES | Documented |
| Vercel free: 150K function invocations | YES | Documented |
| Vercel free: 1 daily cron only | YES | Hourly+ requires Pro ($20) or external cron |
| Supabase free: 500 MB storage | YES | Documented |
| Supabase free: unlimited API requests | YES | Documented |
| Supabase free: pauses after 1 week idle | YES | Documented |
| Neon free: 0.5 GB storage | YES | Documented |
| Globe.gl: free, MIT license | YES | GitHub |
| Globe.gl: supports country polygon clicks | YES | onPolygonClick documented |
| Natural Earth GeoJSON: free, public domain | YES | naturalearthdata.com |
| Trafilatura F1=0.945 | YES | Academic benchmark |
| Claude Haiku: $0.80/$4.00 per M tokens | YES | Anthropic pricing page |
| Claude Sonnet: $3/$15 per M tokens | YES | Anthropic pricing page |
| Morning brief Claude cost: ~$1.50/month | YES | Calculated: 20 stories x 30 days x $0.0024 |
| Free tier total cost: $0/month | YES | With split architecture (Railway backend + Vercel frontend) |
| Paid tier fixed cost: $33-53/month | YES | Calculated from verified API prices |
| Break-even: 4-6 paid subscribers | YES | $40-50 fixed / $10 per sub |

---

## Related Files

- [[SalientSignal-Project]] — Product vision, features, monetization, design direction
- [[SalientSignal-Source-Database]] — 151+ countries, 606+ outlets, all APIs

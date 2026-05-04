---
aliases:
  - SalientSignal Todo
  - SalientSignal Next Steps
tags:
  - apex
  - business
  - app
  - todo
created: 2026-04-10
---

# SalientSignal — Active Todo List

> **Updated: 2026-04-13 — Session 35. MVP path clarified. New data sources researched (Telegram, Grok, VK, Chinese social media). NPS thesis integration concept identified: SalientSignal methodology applied to nuclear signaling. Don deferred all execution to a future session.**

---

## 🔖 NEXT SESSION PICKUP (Session 35, Apr 13)

### MVP Definition — What "Launch-Ready" Means

The free tier MVP is functionally complete. The remaining items to go from "working behind a password" to "public product" are:

1. **Schema v3 migration** (Don, 2 seconds) — paste `shared/migrations/002_country_theme_tables.sql` into Supabase SQL Editor
2. **Theme backfill import** (Don + Claude, 15 min) — re-run full 15-month backfill (~4 hrs background), then import via `import_gkg_backfill.py`
3. **Render cron deployment** (Don, 15 min) — deploy `render.yaml` Blueprint, add 5 env vars. Pipeline stays fresh hourly after this.
4. **Firefox /country/CN hydration bug** (Claude autonomous) — diagnose and fix client-side JS error
5. **`/theme/[code]` cross-country browser** (Claude autonomous) — checkpoint at commit `f96962b`
6. **JAG/ethics review** (Don, scheduling only) — gates removing password gate for public access

Items 1-3 require Don's hands (~20 min total). Items 4-5 are autonomous. Item 6 is non-code.

### New Data Sources — Researched Apr 13, Ready to Build

The following data sources were researched and validated for integration. Build order: Telegram first (fills the biggest gap), then VK, then Grok, then Chinese platforms.

#### Phase 6A: Telegram (Telethon) — $0/mo
- **Library:** Telethon (MIT license, Python 3, MTProto protocol)
- **Capability:** Read ALL messages from any public channel without joining. Real-time monitoring via event handlers. Media download.
- **Requirements:** Register at https://my.telegram.org to get `api_id` and `api_hash` (free, needs phone number)
- **Rate limits:** MTProto (not Bot API). Reading public channels = very generous limits. FloodWaitError auto-handled by Telethon.
- **Why critical:** Russian MoD, Rybar, WarGonzo, Readovka, IRGC-affiliated channels. This fills the GDELT blind spot for Russia/Iran domestic narratives. GDELT barely indexes .ru state media (rt.com=2 articles in full backfill, cctv.com=0). Telegram channels are where the actual domestic IO happens.
- **Don's action:** Register at my.telegram.org, provide `api_id` and `api_hash`

#### Phase 6B: VK API — $0/mo
- **Capability:** All public posts, shares, comments on VKontakte (Russia's dominant social media)
- **Requirements:** Create VK account + register app at vk.com/dev for access token
- **Why critical:** VK is what Russians actually use. RT/Sputnik are export products for international audiences. VK posts are the domestic narrative ground truth.
- **Don's action:** Create VK account if needed, register app, provide access token

#### Phase 6C: Grok x_search (xAI) — ~$0 with data sharing opt-in
- **Capability:** Search ALL public X/Twitter posts via the Responses API. Keyword search, semantic search, user search, thread fetch.
- **Pricing:** $0.20/M input + $0.50/M output tokens (Grok 4.1 Fast). Search tool calls: $2.50-5.00 per 1,000 calls. ~$0.015-0.025 per query total.
- **Free credits:** $25 on signup + **$150/month via data sharing program** (opt-in). Effectively free for MVP-level usage.
- **Architecture:** Tools-based via Responses API (not raw tweet feed). You send a prompt, Grok autonomously searches X, returns LLM-processed response. Means you pay tokens + tool fees.
- **Why useful:** Monitor state media X accounts (@RT_com, @CGTNOfficial, @PressTV, @SputnikInt). Detect coordinated amplification. Gray source detection.
- **Don's action:** Sign up at console.x.ai, get API key, opt into data sharing program for $150/mo credits
- **Deprecated:** Old "Live Search API" with `search_parameters` was deprecated Jan 12, 2026. Must use new Tools-based approach.

#### Phase 6D: Chinese Social Media (TikHub.io) — ~$0-30/mo
- **Problem:** Direct API access to Weibo, WeChat, Douyin from outside China requires Chinese phone + real-name verification. Effectively blocked for foreign developers.
- **Solution:** TikHub.io — third-party aggregator with 700+ endpoints across 14 Chinese platforms (Douyin, Weibo, Bilibili, Xiaohongshu, Kuaishou, WeChat)
- **Pricing:** $0.001 per request. Free daily check-in credits (never expire). $2 credit with invite code.
- **No Chinese phone number required.**
- **Why useful:** Monitors what Chinese state media says on domestic platforms (Douyin, Weibo, Bilibili) where the real domestic narrative lives. CGTN/China Daily/Xinhua English editions are export products.
- **Don's action:** Register at tikhub.io (no credit card required to start)

#### Also Validated (Free, Lower Priority)
- **YouTube Data API v3:** 10K units/day free. State media channels + TranscriptAPI for caption text mining.
- **RSS feeds (feedparser):** Many state news agencies publish clean RSS. Lowest-cost reliable ingestion.
- **Media Cloud (Harvard/UMass):** 2B+ stories, open source, free API. Academic credibility for NPS thesis.

### NPS Thesis Integration Concept (Apr 13)

> **Working title:** "State Media Messaging Divergence as an Indicator of Nuclear Escalation Intent"

SalientSignal's domestic vs. international audience split methodology applied to nuclear signaling:
- When a regime tells its own population one thing about nuclear weapons and the international community another, that gap is the intelligence signal
- Use SalientSignal's pipeline (301 outlets, 81 countries, 15 months of data) as the methodology chapter
- Case studies: Iran (enrichment framing), Russia (tactical nuclear threats), DPRK (test cycles), China (warhead expansion)
- Advisor alignment: Twomey (#1, China/nuclear deterrence) or Volpe (#2, proliferation/coercion)
- Publication potential: genuine research gap at intersection of nuclear studies and IO/information warfare

### Previous Pickup Instructions (Still Valid)

When you're back at the keyboard, you have two parallel paths to SCAME going live. Pick ONE of the first two based on preference:

### Path A — **Re-run the full 15-month backfill** (recommended)
Clean slate, full Jan 2025 → Apr 2026 coverage, ~4 hours wall time in the background while you do other things:
```bash
cd "/Users/don/Documents/Business/Atlas Peak Media, LLC/SalientSignal"
nohup python -m pipeline.scripts.run_gkg_backfill \
    --start-date 2025-01-01 \
    --end-date 2026-04-09 \
    --period monthly \
    --parallelism 20 \
    --output-json pipeline/data/theme_backfill_monthly.json \
    --force > pipeline/logs/theme_backfill_monthly.log 2>&1 &
```
Then: `caffeinate -i -w $(pgrep -f run_gkg_backfill)` to prevent sleep while it runs. Check progress with `tail -5 pipeline/logs/theme_backfill_monthly.log`. Output lands at `pipeline/data/theme_backfill_monthly.json` (~116 MB) when done.

### Path B — **Import the partial JSON as a preview** (faster, less coverage)
The partial from tonight's SIGINT'ed run is already on disk: `pipeline/data/theme_backfill_monthly.json` (2.3 MB, 10,734 buckets, Jan-May 2025, 47 countries, `interrupted=true`). Takes ~5 seconds to import. Dashboard will show 5 months of themes instead of 15. Useful if you want to SEE the SCAME dashboard lit up immediately before committing to a 4-hour re-run. You'd still run the full backfill later.

### 🔴 Steps that are the same either way (Don's hands needed, ~20 min total)
1. **Paste `shared/migrations/002_country_theme_tables.sql`** into Supabase SQL Editor → click Run (2 sec). Creates `country_theme_monthly`, `country_theme_weekly`, `country_theme_daily` tables. Safe to re-run (all `IF NOT EXISTS`).
2. **Dry-run validate the JSON:** `python -m pipeline.scripts.import_gkg_backfill --input-json pipeline/data/theme_backfill_monthly.json --dry-run` — 6 validation passes should all pass.
3. **Real import:** `python -m pipeline.scripts.import_gkg_backfill --input-json pipeline/data/theme_backfill_monthly.json --interactive`. SCAME dashboard lights up INSTANTLY after import — no redeploy needed, pages are `dynamic='force-dynamic'`.
4. **Sync the Render Blueprint** (10 min). `render.yaml` has a second cron service `salientsignal-themes` at :17 past the hour. Go to Render dashboard → Blueprint → Sync. Paste env vars for the new service. Theme data stays fresh hourly from then on.
5. **Full step-by-step runbook:** `docs/THEME_PIPELINE_DEPLOYMENT.md`

### 🟡 Autonomous next session work
- **Resume `/theme/[code]` cross-country browser route** — flip the browsing model from "what's Country X pushing" to "who's pushing Theme Y". Commit `f96962b` landed the `getThemeLabel()` helper in `src/lib/data.ts`. Still needs:
  - `src/app/theme/[code]/page.tsx` — new route, takes a GDELT theme code, shows cross-country bar chart + narrative + time trend
  - `src/lib/data.ts::getThemeAcrossCountries(themeCode, period)` — queries `country_theme_monthly` where theme=X, returns all (country, audience, periodStart, count) rows ordered by article_count desc
  - Wire the Trending Themes panel on the home page so each theme label becomes a clickable link to `/theme/[code]`
  - Add the route to the methodology page footer or the header nav
- **Firefox /country/CN hydration check** — the B7 Clock extraction fix should have resolved the 2 console errors, but verify with a real Firefox session once the site has actual data to render.
- **Optional polish:** methodology page ToC with clickable anchor links, home page "Biggest Movers" subtitle referencing z-score direction, SCAME panel loading skeleton.

### 🟢 Launch blockers (not code)
- **JAG/ethics review** — still the gate for removing the password gate. Schedule alongside the Loki + Atlas Peak Capital review.
- **Anthropic API key + $20 credit** — needed before paid-tier AI debrief paragraphs ship (currently using zero-LLM template narratives so not blocking the MVP).

---

## ✅ BACKFILL IMPORT COMPLETE (Apr 10, 23:38 local)

**Historical backfill:** `pipeline/data/backfill.json` (26 MB, 52,432 rows)
- Date range: 2025-01-01 → 2026-04-09 (464 days)
- Countries: 81 unique
- Outlets queried: 301 (172 → 301 after Tier 2 expansion)
- Outlets succeeded: 301 (100%)
- Outlets empty: 164 (expected — GDELT Tier 1 coverage gap: rt.com=2, cctv.com=0, cgtn.com=0, people.com.cn=0)
- Outlets failed: 0
- Audience split: 36,192 DOMESTIC / 15,776 INTERNATIONAL / 464 DIASPORA
- Level histogram: 38,223 neutral / 10,937 coolGray / 853 amber / 815 steelBlue / 801 red / 511 orange / 292 deepBlue — real spikes AND dips detected

**Dry-run validation:** all 6 passes succeeded (schema, values, date coverage, sanity events warn-only, volume ceiling, FVEY exclusion).

**Sanity event warnings (expected, documented):** Feb 24 2026 Ukraine anniversary, May 9 2025 Victory Day, Oct 1 2025 China National Day are all present in the data but NOT showing elevated activity because rt.com/cctv.com/cgtn.com/people.com.cn — the outlets that would spike — returned essentially nothing from GDELT. The baselines themselves are correct; these anniversaries just rely on outlets GDELT doesn't index well. Grok supplement (post-MVP) will fill this gap.

**Supabase import:**
- 525 batches × 100 rows = 52,432 rows upserted
- 791 historical cold_start rows flipped to `cold_start=FALSE`
- Final Supabase state: **52,440 total rows** across 81 countries (52,432 backfill + 8 from Apr 10 Phase 2 live run)
- 8 remaining cold_start rows are the Apr 10 current-day Phase 2 rows (will clear when pipeline runs again)
- Import manifest: `pipeline/data/backfill_import_manifest_20260411T003800Z.json`

**Site verification (curl):** `https://salientsignal.com/` → `HTTP/2 307 → /login` with `x-vercel-cache: MISS` (fresh render). Code path hits Supabase on every request because home page is `dynamic='force-dynamic'` + `runtime='nodejs'`.

---

---

## Current State

**STATUS: LIVE** at `https://salientsignal.com`, password-gated, noindex'd. Running on a fresh Vercel project (the original accumulated 8+ hours of broken state and had to be nuked). Repo has been restructured so `package.json` sits at the root like APM and FGF. Middleware was deleted and replaced with per-page `requireAuth()` because Vercel's Edge Runtime bundling had MIDDLEWARE_INVOCATION_FAILED bugs specific to this project. **12 commits pushed** to `origin/main` on Apr 10:

- ✅ **Phase 0:** Repo + Vercel + Supabase project created
- ✅ **Phase 0.5:** Next.js frontend scaffold with dummy data deployed
- ✅ **Phase 1:** Pipeline code + 15 CRITICAL red team fixes + Anti-Hallucination Agent + 56 unit tests (commit `0e01c9d`)
- ✅ **Phase 2 code work:** 20 red team fixes (10 CRITICAL + 10 HIGH) + verification infrastructure + cold start handling + 83 new tests (commit `e659c8d`)
- ✅ **Phase 2 execution:** Schema applied, outlets seeded, Tier 1 → Tier 2 → Full scale all SUCCEEDED (Apr 10)
- ✅ **Phase 2 live-run hotfixes:** `_caveat` stripping, GDELT language ISO mapping, state-media filter (commit `971b362`)
- ✅ **Phase 4:** Unified data adapter + server-side Supabase client + ColdStartBanner + server/client split + country page refactor (commit `03f1134`)
- ✅ **Subdomain classification fix:** 11 new subdomain entries + 1 reclassification + 11 regression tests (commit `21fc241`)
- ✅ **Force-dynamic fix** (commit `fee5a17`): pages `dynamic='force-dynamic'` + `runtime='nodejs'`, improved data.ts error logging
- ✅ **Middleware debugging arc** — defensive rewrite (`8e05812`), minimal diagnostic (`db0ff22`), both still failed. Proved Vercel Edge Runtime bundling bug specific to this project, not our logic.
- ✅ **Repo restructure** (commit `8d27cce`): moved 28 tracked files from `web/` to repo root via `git mv` preserving history. Matches APM/FGF single-project layout.
- ✅ **Middleware bypass with per-page requireAuth** (commit `708b214`): deleted `middleware.ts`, created `src/lib/auth.ts` with server helpers, added `await requireAuth()` to home + country pages
- ✅ **Localhost proof of life** — started local prod server on port 3458, every route behaved correctly. Proved the code was 100% fine.
- ✅ **Custom domain salientsignal.com** added to Vercel, DNS updated in Squarespace (`A @ → 76.76.21.21`, `CNAME www → cname.vercel-dns.com`)
- ✅ **Nuke and recreate the Vercel project** — deleted the broken `salient-signal` project, imported fresh from GitHub with Next.js preset and blank Root Directory, re-added 5 env vars, added domains, deployed. **First build on the fresh project worked perfectly. This was the actual fix.**
- ✅ **Live verification curl** — apex/www 307→/login, /login 200, /country/CN 307 (unauth) or 200 (with cookie), `x-robots-tag: noindex` on every response. Site is **LIVE**.
- ✅ **Globe visual overhaul v1** (commit `c5c3c00`): brighter material, atmosphere, visible borders, hover state, reduced-motion
- ✅ **Globe visual overhaul v2** (commit `f8bccc9`): reverted country fill to dark after user feedback (v1 conflicted with legend colors), made borders bold tealMax full opacity, pure white on hover, teal-tinted polygon sides, slight altitude lift. "Dark terrain with glowing boundaries" look.
- ⏳ **Firefox /country/CN bug** (next session): 2 client-side JS console errors break hydration after clicking a country. RSC fetch returns 200 (5.08 KB), network is fine. Need Console tab screenshot to diagnose.
- ⏳ **Phase 3:** Render cron deployment (not started — needs Don's Render login). Supabase data is getting stale without hourly refresh.
- ⏳ **Hybrid ingestion for locked-down states** (Phase 5): Iran/DPRK/Cuba/Belarus won't ingest via country filter — needs domain-fallback mode. Architectural finding documented below.

**Total tests:** 151 passing (56 Phase 1 + 83 Phase 2 + 1 hotfix regression + 11 subdomain override).
**Total outlets:** 172 in `outlets.json`.
**Total commits today:** 12, all pushed to `origin/main`: `0e01c9d`, `e659c8d`, `971b362`, `03f1134`, `21fc241`, `fee5a17`, `8e05812`, `db0ff22`, `8d27cce`, `708b214`, `c5c3c00`, `f8bccc9`

**Real data in Supabase:** 118 unique articles across 8 country buckets (CN 50, RU 35, TR 14, TW 11, DE 4, KH 4). All cold_start=True, all level=neutral (no baseline yet). Storage: 0.2% of free tier. **Stale** — no runs since Apr 10 initial load. Phase 3 Render cron will fix this.

---

## ✅ Phase 2 EXECUTION COMPLETE (Apr 10, 2026)

All Phase 2 execution steps completed successfully. See [[SalientSignal-Phase2-Review]] for full metrics.

- [x] Schema applied to Supabase — "Success. No rows returned"
- [x] `verify_schema.py` PASSED (10 tables, schema_version=2, 0% storage)
- [x] `gdelt_probe.py` PASSED (p50 9s, 6/6 columns, subdomain walk-up confirmed)
- [x] 161 outlets seeded, all 7 Tier 1 spot checks pass, 0 FVEY leaks
- [x] Tier 1 dry-run (0.5s)
- [x] Tier 1 LIVE run: 77 state-media articles from 456 raw GDELT (17% signal, 23.6s)
- [x] `verify_first_run.py` PASSED
- [x] 20 classifications spot-checked — all legit state media (Xinhua, China Daily, Izvestia, Vesti, RIA, RT)
- [x] Tier 2 expansion: 89 articles from 658 raw (184s)
- [x] Full 70-country scale run: 105 articles from 2,478 raw in 16.3 minutes
- [x] 3 live-run hotfixes applied (`_caveat` strip, GDELT language ISO map, state-media filter)
- [x] Phase 2 Review report updated with execution metrics

**Final Supabase state:** 118 unique articles across 8 country buckets. 15 analysis_claims audit rows. 3 pipeline_runs all SUCCESS. 0.2% storage.

**Data captured by country:**
- CN: 50 (19 DOMESTIC + 31 INTERNATIONAL)
- RU: 35 (34 DOMESTIC + 1 INTERNATIONAL)
- TR: 14 (DOMESTIC — TRT)
- TW: 11 (DOMESTIC — Taiwan CNA)
- DE: 4 (INTERNATIONAL — Deutsche Welle)
- KH: 4 (DOMESTIC — Cambodia)

**Languages captured (all valid ISO 639-1):** en(36), ru(35), zh(25), tr(14), fr(5), sw(2), es(1)

---

## Phase 3 — Render Cron Deployment (Claude autonomous)

- [ ] Create Render account (if not already)
- [ ] Create Background Worker service connected to `AtlasPeakMedia/SalientSignal`
- [ ] Configure cron schedule: `0 * * * *` (every hour at :00)
- [ ] Set Python runtime with `pip install -e pipeline/`
- [ ] Add Render environment variables (SUPABASE_URL + SUPABASE_SECRET_KEY)
- [ ] Trigger first manual run
- [ ] Verify pipeline_runs row lands in Supabase
- [ ] Enable automatic cron schedule
- [ ] Monitor 24 hours of runs (24 × SUCCESS rows)
- [ ] Add Render health probe alerting

---

## ✅ Phase 4 COMPLETE (Apr 10 night, commit `03f1134`)

Frontend now reads from Supabase behind a feature flag. Safe-default keeps dummy data until the Vercel env var is flipped.

**Files added (6):**
- `web/src/lib/types.ts` — canonical shared types (CountryActivity, AudienceActivity, Headline, CoordinationArc, TrendingTheme, DeviationLevel, Confidence)
- `web/src/lib/supabase.ts` — server-only Supabase client factory. Reads either `SUPABASE_URL`/`SUPABASE_SECRET_KEY` or the legacy `NEXT_PUBLIC_SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` names
- `web/src/lib/countries-meta.ts` — ISO2 → {name, flag, region} lookup built from the 151-country dummy fixture (so Supabase rows can hydrate with display metadata)
- `web/src/lib/data.ts` — unified data adapter with `server-only` guard. Every page and component reads through `getAllCountryActivity()`, `getCountryActivityByCode()`, `getCountryHeadlines()`, `getCoordinationArcs()`, `getTrendingThemes()`, `isUsingDummyData()`. Each helper routes to dummy OR live Supabase based on `NEXT_PUBLIC_USE_DUMMY_DATA`
- `web/src/app/HomePageClient.tsx` — new client component holding `viewMode` state and rendering globe/controls/movers
- `web/src/components/ColdStartBanner.tsx` — explains the baseline calibration period

**Files refactored (6):**
- `web/src/app/page.tsx` — now a server component that parallel-fetches all three datasets (`getAllCountryActivity`, `getCoordinationArcs`, `getTrendingThemes`) and passes them as props. `revalidate = 300` matches the hourly pipeline cadence
- `web/src/app/country/[code]/page.tsx` — awaits the data layer, returns `notFound()` for un-ingested countries, added a Top Outlets section rendering `country_activity.top_outlets` JSONB, headlines are now clickable anchors to the source article
- `web/src/components/Globe/GlobeWrapper.tsx` — takes `countryActivity` and `coordinationArcs` as props instead of importing the fixture. Tooltip now shows total article count and a "cold start" tag
- `web/src/lib/dummy-data.ts` — deduplicated: type definitions moved to `types.ts`, now just re-exports types + provides the static fixture
- `web/src/lib/colors.ts` — imports `DeviationLevel` from `types.ts`
- `web/.env.example` — updated to document all four env var names

**Dependencies added:** `@supabase/supabase-js`, `server-only`

**Build:** `npm run build` succeeds with zero TypeScript errors. Route map:
```
Route (app)          Revalidate  Expire
┌ ○ /                        5m      1y
├ ○ /_not-found
└ ƒ /country/[code]
```

**Local smoke test results** (`NEXT_PUBLIC_USE_DUMMY_DATA=false`, `npm run dev --port 3457`):
- `GET /` → HTTP 200, shows all 6 live countries (CN, DE, KH, RU, TR, TW) in top movers, "COLD START" header badge, "Baseline calibration" banner, "LIVE DATA" footer
- `GET /country/CN` → HTTP 200, renders real clickable Chinese state-media headlines from `edu.people.com.cn`, `xinhuanet.com`, `africa.chinadaily.com.cn`
- `GET /country/RU` → HTTP 200, renders real `ria.ru` and `russian.rt.com` headlines
- `GET /country/UY` → HTTP 404 (correct — Uruguay has no ingested data)

**What this does NOT change:** `NEXT_PUBLIC_USE_DUMMY_DATA=true` is still the Vercel value from Phase 0.5, so `salient-signal.vercel.app` continues showing the dummy globe until the flag is flipped. No production surprises from the commit landing.

### Follow-on items

- [ ] **Flip `NEXT_PUBLIC_USE_DUMMY_DATA=false` in Vercel** after reviewing the commit (activates real-data path)
- [ ] **Push 5 commits** to `origin/main`: `0e01c9d`, `e659c8d`, `971b362`, `03f1134`, `21fc241`
- [x] **Subdomain classification override** — commit `21fc241` (Apr 10 night). Added 11 explicit subdomain entries (`russian.rt.com` as DOMESTIC, 10 Chinese foreign-language editions as INTERNATIONAL) that beat the parent walk-up. Reclassified `deutsch.rt.com` DIASPORA → INTERNATIONAL. 161 → 172 outlets. 11 new regression tests. 151 tests total passing. No code change required — the existing `get_outlet()` already tries exact hostname match before walking up, so it's pure data.
- [ ] **Empty state for countries with no ingested articles** — country page currently 404s; could instead show a friendly "not yet monitored" page with a back link

---

## Phase 5+ — Polish and Launch Prep (deferred)

- [ ] Methodology page content (long-form explainer)
- [ ] About page
- [ ] Country descriptions (195 countries, ~$5 one-time Claude API cost)
- [ ] Outlet descriptions (top 200 outlets, ~$5 one-time Claude API cost)
- [ ] Theme labels (GDELT codes → human readable)
- [ ] Loading states, skeletons, empty states
- [ ] Mobile polish
- [ ] Lighthouse Performance > 90, Accessibility > 95
- [ ] First-visit inline tutorial
- [ ] SEO metadata + sitemap + OG image

---

## Paid AI Services — What's Needed to Run the Program

**Current state (Apr 10):** ZERO paid AI services required. The pipeline (classifier, deviation, coordination detection, anti-hal) is 100% rule-based. The frontend makes no LLM calls. The only Anthropic reference in the whole codebase is a one-line TODO comment in `antihal.py` about a future Phase C enhancement. Everything that's shipped can run on $0/month AI spend.

**What needs a paid API key BEFORE certain features ship:**

### 1. Anthropic API key (Claude) — REQUIRED for paid tier features

The product spec (see [[SalientSignal-Project]] and [[SalientSignal-User-Stories]]) positions AI-generated debrief paragraphs as the $10/mo tier's core value. Those debriefs run through Claude with SCAME prompts internally (never shown to the user). Four usage sites, all via the same API key:

- [ ] **AI debrief paragraphs** — Generate the per-country daily summary that sits above the audience split on the country page. Core paid-tier feature. Daily cost scales with paid subscribers × countries they view.
- [ ] **Theme labels** — Translate GDELT's cryptic `WB_2024_ANTI_WESTERN_PROPAGANDA` codes into human-readable labels. One-time batch run (~200 themes), <$1 total, cacheable forever.
- [ ] **Country descriptions** — One paragraph per monitored country explaining its media ecosystem and state-media landscape. ~195 countries × one Claude call each. ~$5 one-time, regenerate quarterly if needed.
- [ ] **Outlet descriptions** — One paragraph per top-200 outlet (ownership, state alignment, typical editorial line). ~$5 one-time, cacheable.

**Action item:** Sign up at console.anthropic.com, generate an API key, store as `ANTHROPIC_API_KEY` in Vercel env vars (for frontend debrief calls via server component) and in Render env vars (for any pipeline-side content generation). Expected monthly cost at launch: **$0-15**, scaling with paid subscribers. Pre-paid $20 credit covers all one-time batch jobs with margin.

### 2. ElevenLabs / text-to-speech — NOT NEEDED

SalientSignal is text/visual only. No audio.

### 3. Embedding models — NOT NEEDED for MVP

Coordination detection currently uses TF-IDF + entity overlap (pure Python, no API). If we upgrade to semantic similarity in Phase 6, we'd use `claude-haiku` or OpenAI embeddings — but that's optional and distant.

### 4. Sentry / logging / monitoring — optional, free tier sufficient

Not AI, but worth noting in the same "paid services to check" sweep. Sentry free tier (5K events/month) is enough for an MVP. Add only if we hit volume.

### Summary table

| Service | Required for MVP? | Required for paid tier? | One-time cost | Monthly cost |
|---------|:-----------------:|:-----------------------:|:-------------:|:------------:|
| Anthropic API (Claude) | No | **Yes** | ~$10 (country + outlet + theme batches) | $0-15 scaling with subs |
| OpenAI | No | No | — | — |
| ElevenLabs | No | No | — | — |
| Embeddings | No | No (MVP), maybe Phase 6 | — | — |
| Sentry / monitoring | No | No | — | Free tier |

**Pre-launch blocker for paid tier:** Yes — need Anthropic API key + ~$20 credit before public launch. **NOT a blocker for Phase 3 (Render cron) or Phase 4 (flip the Vercel flag)** — those ship on free tier alone.

---

## Blockers (not code work)

- [ ] **JAG / ethics review** — Schedule alongside Loki + Atlas Peak Capital consultation. Blocks public launch.
- [ ] **Domain registration** — Defer until JAG sign-off. Candidates: salientsignal.com / .io / .media
- [ ] **Supabase Project URL** — Need the actual URL from Settings → Data API

---

## Launch Sequence (post-JAG)

### Soft Launch (Week 1)
- [ ] Share with Don's 2-3 trusted reviewers (Delta contacts, IWI advisor, trusted journalist/academic)
- [ ] No public posts

### Friends & Family Launch (Week 2)
- [ ] Personal outreach to ~10-20 contacts
- [ ] MCIOC colleagues
- [ ] Apex collaborators

### .mil Community Launch (Week 3-4)
- [ ] Reddit r/OSINT, r/intel, r/military_intelligence
- [ ] Direct outreach to IO/PSYOP communities
- [ ] Quote Hamilton 2.0 shutdown as the gap being filled

### Broader Launch (Week 5+)
- [ ] Bellingcat / OSINT Curious community
- [ ] Academic IR / political science networks
- [ ] Disinformation reporting community

### Press Outreach (Week 6+)
- [ ] Wired, The Atlantic, Foreign Policy pitches
- [ ] Just Security, Lawfare
- [ ] "The gap left by Hamilton 2.0 just got filled" angle

---

## Cost Status

| Component | Free Tier | Current Usage | Cost |
|-----------|-----------|---------------|------|
| Vercel (frontend) | 100 GB bandwidth | ~0 | $0 |
| Supabase (database) | 500 MB | 0.2% | $0 |
| Render (cron) | 750 hrs/month | 0 (not deployed) | $0 |
| GDELT API | no limit published | ~100 queries/run | $0 |
| Anthropic API (Claude) | — | 0 (not yet integrated) | **$0 today, $0-15/mo post-launch** |
| Domain | — | not registered | $0 |
| **TOTAL** | | | **$0/month today** |

The MVP runs on $0/month. Anthropic API is the only paid AI dependency, and only for paid-tier features (AI debrief paragraphs) + one-time content batches (country descriptions, outlet descriptions, theme labels). Est. $10 one-time + $0-15/mo scaling with paid subscribers. See the "Paid AI Services" section above for the full breakdown and action items.

---

## Risk Watch

- **GDELT rate limit unknown** — will be measured by `gdelt_probe.py` on Step 3
- **Cold start false alarm** — operator must read `COLD_START.md` before panicking
- **Supabase free tier full at ~60 days** — need manual purge script (Phase 3 work)
- **Domain normalization hit rate** — if probe shows <30%, fix before scale-up

---

## Architectural finding (logged Apr 10 night) — GDELT sourcecountry filter is unreliable for locked-down states

**Discovered** during a direct probe after the Phase 2 full scale run returned zero articles for Iran despite 11 registered Iranian outlets.

**What we tested**

1. `sourcecountry:IR` country filter — returned 0 articles in the Phase 2 live run and still 0 on subsequent probes (rate-limited, but previous passes confirmed empty)
2. `domain=presstv.ir` direct query — returned 5 real Press TV articles with `sourcecountry="Iran"`
3. `sourcecountry:KN` (DPRK) — returned 17 articles, **all from `northkoreatimes.com`**, which is a Filipino/Western aggregator *about* North Korea, not actual DPRK state media
4. `sourcecountry:CN` — works fine, returned all our Chinese state media
5. `sourcecountry:RU` — works fine

**Conclusion**

GDELT's country filter works for open-internet countries but fails for states whose media is hard to crawl (firewalled, sanctioned, intermittent availability). For Iran, DPRK, Cuba, Belarus, and similar countries we can't rely on `sourcecountry` as the ingestion pathway. The articles are there in GDELT — we just have to ask for them by domain.

**Fix (Phase 5 architectural work, NOT in this MVP)**

Hybrid ingestion mode in `pipeline.py`:
1. For each monitored country, run the existing `country=XX` query first
2. If the returned article count (after state-media filter) is below a threshold (say, 3 articles), fall back to iterating over the registered outlet domains for that country and querying each directly via `domain=X`
3. Deduplicate merged results at the URL level
4. Accept the additional GDELT query volume (~5-15 extra queries per empty country)

Estimated implementation: ~2-3 hours. Adds ~200 queries to the full scale run, still well within the 50-minute budget. Will light up Iran, DPRK, Cuba, Belarus, and other sanctioned-media countries.

**Do not do this now** — it requires the Phase 3 Render cron to be deployed first so we can measure the real rate-limit envelope in production, and the subdomain fix just shipped is the more visible win for the dataset we already have.

---

---

## Related Files

- [[SalientSignal-Project]] — Product vision
- [[SalientSignal-Phase1-Review]] — Phase 1 completion (15 CRITICAL fixes)
- [[SalientSignal-Phase2-Review]] — Phase 2 completion (20 more fixes)
- [[SalientSignal-Algorithms]] — Algorithm pseudocode
- [[SalientSignal-Way-Ahead]] — 100-task roadmap
- Cold start runbook: `pipeline/COLD_START.md`
- Plan file: `/Users/don/.claude/plans/proud-jumping-key.md`

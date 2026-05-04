---
aliases:
  - SalientSignal Way Ahead
  - SalientSignal Roadmap
  - SalientSignal 100-Task Plan
tags:
  - apex
  - business
  - app
  - roadmap
created: 2026-04-09
---

# SalientSignal — Way Ahead

> **100 pure app-iteration tasks. Infrastructure, code, data, content, UX, performance, features. Legal and marketing handled separately by Don — not in this list.**

---

## Current State (as of 2026-04-09 evening)

- ✅ 5 spec files complete in vault
- ✅ Repo at `/Users/don/Documents/Business/Atlas Peak Media, LLC/SalientSignal/`
- ✅ GitHub `AtlasPeakMedia/SalientSignal` (private) — 3 commits pushed
- ✅ Frontend scaffold — Next.js 16 + React 19 + Tailwind 3 + react-globe.gl. Build passes.
- ✅ Vercel project created, fresh build in progress
- ✅ Supabase project created (keys received, URL pending)
- 🔄 Phase 1+2 Python pipeline — background agent building
- ⏳ Render account — not yet created

---

## Phase 0 — Infrastructure Completion (Tasks 1-10)

*Get the frontend live on Vercel with dummy data, Supabase provisioned, Render ready.*

- [ ] **1.** Resolve Vercel 404 — verify the latest deployment (`958a344`) builds from `web/` and serves at `salient-signal.vercel.app`
- [ ] **2.** If still 404: read Vercel build logs, identify root cause, fix and redeploy
- [ ] **3.** Confirm production alias `salient-signal.vercel.app` points to the latest successful deployment
- [ ] **4.** Get Supabase Project URL from Settings → Data API (format `https://[ref].supabase.co`)
- [ ] **5.** Update `NEXT_PUBLIC_SUPABASE_URL` in Vercel environment variables
- [ ] **6.** Update `web/.env.local` with real Project URL for local dev
- [ ] **7.** Trigger Vercel redeploy with real Supabase URL, verify site still works
- [ ] **8.** Create Render account, sign in with GitHub
- [ ] **9.** Connect Render to the GitHub repo (no cron job yet)
- [ ] **10.** Enable Vercel Analytics + Speed Insights on the project

---

## Phase 1 — Pipeline Code Review (Tasks 11-20)

*Review and validate the Python pipeline code produced by the background agent.*

- [ ] **11.** Review `pipeline/data/outlets.json` — 150+ entries, all Tier 1 countries covered, valid schema
- [ ] **12.** Spot-check outlet classifications: RT international, TASS.ru domestic, TASS.com international, CGTN international, CCTV domestic, Press TV international, IRNA domestic
- [ ] **13.** Review `shared/countries.json` — FIPS↔ISO mapping for all 195 countries with official languages and regions
- [ ] **14.** Review `pipeline/src/outlets.py` — lookup functions work correctly
- [ ] **15.** Review `pipeline/src/classifier.py` — Algorithm 1 implementation (outlet → language → platform → TLD fallback with confidence scoring)
- [ ] **16.** Review `pipeline/src/gdelt_client.py` — rate limiting, exponential backoff on 429 errors
- [ ] **17.** Review `pipeline/src/baselines.py` — 30-day rolling mean/std calculation, edge cases
- [ ] **18.** Review `pipeline/src/deviation.py` — ratio + z-score + color level mapping matches spec
- [ ] **19.** Review `pipeline/src/coordination.py` — cross-country spike detection, time window filtering, scoring
- [ ] **20.** Review `pipeline/src/pipeline.py` — main orchestration flow: query → classify → store → recalculate → detect → update

---

## Phase 2 — Database + Local Testing (Tasks 21-30)

*Initialize Supabase schema, run pipeline locally, verify real GDELT data flows correctly.*

- [ ] **21.** Review `shared/schema.sql` against MVP subset from Algorithms spec
- [ ] **22.** Initialize Supabase database by running `shared/schema.sql` via SQL Editor
- [ ] **23.** Verify all tables created (outlet_classification, articles, country_activity, coordination_events, daily_snapshots)
- [ ] **24.** Verify database indices exist (country+date, audience_type, domain)
- [ ] **25.** Run `pipeline/scripts/seed_outlets.py` to populate outlet_classification table
- [ ] **26.** Run `pipeline/scripts/run_pipeline.py --dry-run` — verify stage outputs, no errors
- [ ] **27.** Run live pipeline — verify articles + country_activity populate
- [ ] **28.** Query Supabase: verify 200-500+ articles from Tier 1 countries with correct audience classifications
- [ ] **29.** Spot-check 20 random classifications from real data — RT English international, TASS Russian domestic, etc.
- [ ] **30.** Tune deviation thresholds if real data shows color mapping is off

---

## Phase 3 — Render Cron Deployment (Tasks 31-40)

*Deploy pipeline to Render as automated hourly cron job.*

- [ ] **31.** Create Render "Cron Job" service from the GitHub repo
- [ ] **32.** Configure cron schedule `7 * * * *` (hourly at :07)
- [ ] **33.** Set build command: `cd pipeline && pip install -r requirements.txt`
- [ ] **34.** Set start command: `cd pipeline && python scripts/run_pipeline.py`
- [ ] **35.** Add environment variables: `SUPABASE_URL`, `SUPABASE_SECRET_KEY`
- [ ] **36.** Trigger first manual cron run via Render dashboard
- [ ] **37.** Wait for first automated hourly run, verify schedule fires
- [ ] **38.** Monitor Render logs for errors over 24 hours
- [ ] **39.** Add pipeline health monitoring: `pipeline_runs` table tracks timestamp + article count + errors per run
- [ ] **40.** Verify Render free tier usage (144 hrs/month ≪ 750 free hrs)

---

## Phase 4 — Frontend + Real Data Integration (Tasks 41-50)

*Wire the frontend to Supabase instead of dummy data fixture.*

- [ ] **41.** Create `web/src/lib/supabase.ts` — server-side Supabase client
- [ ] **42.** Create API route `/api/globe-data` — returns country activity array for globe
- [ ] **43.** Create API route `/api/country/[code]` — returns country detail with headlines and themes
- [ ] **44.** Create API route `/api/coordination` — returns coordination arcs
- [ ] **45.** Add feature flag logic: `NEXT_PUBLIC_USE_DUMMY_DATA` toggles dummy vs real
- [ ] **46.** Update `GlobeWrapper.tsx` to fetch from `/api/globe-data` instead of importing dummy-data directly
- [ ] **47.** Update `country/[code]/page.tsx` to fetch from API via server component
- [ ] **48.** Add loading skeleton for globe (while API fetch is in flight)
- [ ] **49.** Add error boundary — graceful error message on Supabase query failure
- [ ] **50.** Flip feature flag to `false` in Vercel, verify everything works end-to-end with real data

---

## Phase 5 — Data Quality + Content Display (Tasks 51-60)

*Validate data quality, build out content layer (theme labels, country descriptions, freshness indicators).*

- [ ] **51.** Let pipeline run for 14 days to accumulate baseline data (spot-check daily)
- [ ] **52.** Build `pipeline/scripts/audit_classifications.py` — samples 50 random articles/day for human review
- [ ] **53.** Review and fix misclassifications identified during audit, update `outlets.json`
- [ ] **54.** Build `pipeline/data/theme_labels.json` — map top 100 GDELT theme codes to human-readable labels
- [ ] **55.** Update `themes.py` to translate GDELT codes to human labels when writing to country_activity
- [ ] **56.** Build `pipeline/data/country_descriptions.json` — Claude-generated 2-3 sentence overview per country (~$5 one-time)
- [ ] **57.** Build `pipeline/data/outlet_descriptions.json` — Claude-generated 1-2 sentence description per top 100 outlets (~$3 one-time)
- [ ] **58.** Display country descriptions on country pages (new `CountryOverview` component)
- [ ] **59.** Display outlet descriptions in tooltips on hover over outlet names
- [ ] **60.** Add "last updated" timestamp to frontend — pulls from `pipeline_runs`, shows banner if >2 hours stale

---

## Phase 6 — UX Polish (Tasks 61-70)

*First-visit experience, explainability, accessibility, performance.*

- [ ] **61.** Add inline first-visit tutorial on globe — dismissible overlay: "Tap any country to see what its state media is publishing today. Try Russia →"
- [ ] **62.** Add tooltips explaining deviation ratios and z-scores (hover the stat badges)
- [ ] **63.** Add coordination arc click handler — modal shows theme, countries, headlines side-by-side, confidence score
- [ ] **64.** Build country search bar — fuzzy search for small countries hard to tap on globe
- [ ] **65.** Mobile responsiveness audit — test iPhone 12+, Android, iPad. Fix any layout breaks.
- [ ] **66.** Keyboard navigation — Tab through countries, Enter opens country page, Esc closes modals
- [ ] **67.** Screen reader support — ARIA labels on globe polygons, country names, audience split columns
- [ ] **68.** Reduced motion support — respect `prefers-reduced-motion` across all animations
- [ ] **69.** Globe performance optimization — lazy load Three.js bundle, test <1s initial render on mobile
- [ ] **70.** Lighthouse audit: Performance >90, Accessibility >95, SEO >95

---

## Phase 7 — Content Pages + Features (Tasks 71-80)

*Content pages users see in the app + additional features. App-side content only.*

- [ ] **71.** Build methodology page (`/methodology`) — explains data sources, classification, limitations. Written to be read, not to satisfy lawyers.
- [ ] **72.** Build about page (`/about`) — brand identity, mission, what the product does and doesn't do
- [ ] **73.** Build sources attribution page (`/sources`) — credits GDELT, Natural Earth, State Media Monitor (CEU), Wikipedia
- [ ] **74.** Build FAQ / help page — common questions, "how do I read this," "what does [term] mean"
- [ ] **75.** Build theme detail pages — tap any theme tag, see frequency chart + countries pushing it + sample headlines
- [ ] **76.** Build country comparison view — select 2-3 countries, see their activity side-by-side
- [ ] **77.** Build regional zoom on globe — pinch into a region, see country-level detail without tapping individually
- [ ] **78.** Build empty state polish — countries with no data, pipeline failures, new/unmonitored countries
- [ ] **79.** Build 404 page — dark themed, country list as suggestions, "Jump to a country" search
- [ ] **80.** Add keyboard shortcuts (`?` to show help, `/` to focus search, arrow keys to navigate globe)

---

## Phase 8 — Pre-Launch Tech Validation (Tasks 81-90)

*Final technical validation before launch. Acceptance tests, performance, cross-browser, analytics.*

- [ ] **81.** Run all 7 acceptance test cases from the plan file (Russia anti-NATO, China Taiwan surge, Belarus quiet, coordination detected, silence signal, cross-audience contradiction teaser, first-time user comprehension)
- [ ] **82.** Test edge cases: country with no data, broken polygon, API timeout, JavaScript disabled, slow 3G
- [ ] **83.** Cross-browser testing: Chrome, Safari, Firefox, Edge (desktop). Chrome Android, Safari iOS (mobile).
- [ ] **84.** Real device testing: iPhone 12+, iPad, Android phone, large desktop monitor
- [ ] **85.** Security audit: `npm audit`, secret scan of git history, verify no exposed keys
- [ ] **86.** Performance audit: final Lighthouse scores (90+/95+/95+), First Contentful Paint <1s, Time to Interactive <2s
- [ ] **87.** Add Open Graph + Twitter card meta tags (og:image, og:title, og:description per page)
- [ ] **88.** Generate og-image.png (1200x630 globe visualization)
- [ ] **89.** Add error tracking — Sentry free tier or simple error logging to Supabase
- [ ] **90.** Add sitemap.xml generator + favicon set (16, 32, 192, 512) + web manifest for PWA install

---

## Phase 9 — Launch + Monitoring (Tasks 91-100)

*Domain, custom URL, post-launch monitoring, iteration cycles.*

- [ ] **91.** Register domain (salientsignal.com / .io / .media / .news) via Porkbun or Namecheap
- [ ] **92.** Configure DNS pointing to Vercel (A records or CNAME per Vercel instructions)
- [ ] **93.** Add custom domain to Vercel project, verify SSL auto-provisions
- [ ] **94.** Update internal references to use the new domain (README, spec files, env vars)
- [ ] **95.** Set up uptime monitoring — UptimeRobot or similar free service checking homepage every 5 min
- [ ] **96.** Set up pipeline failure alerts — email if cron job fails 2 runs in a row
- [ ] **97.** Set up weekly metrics review cadence — unique visitors, country page views, engagement, pipeline health
- [ ] **98.** First iteration cycle (post-launch week 1) — fix any user-reported bugs within 24 hours
- [ ] **99.** First content expansion (post-launch week 2) — add 50 more outlets from the source database (150→200)
- [ ] **100.** Month 1 retrospective — what's working, what's not, what to build next from the post-launch iteration list

---

## Post-Launch Iteration (Not counted in the 100)

These are v1.1+ app features from the [[SalientSignal-User-Stories]] gap analysis. Build after validating MVP traction.

### Historical Archive
- Calendar view — tap any date, see that day's globe + brief
- Trend explorer with time slider — animate globe through last 30/90/365 days
- Full-text search across archive
- Weekly/monthly digest auto-generation
- PDF export for briefs and digests

### AI Analysis Layer
- Claude API integration for debrief paragraph generation on country pages
- Cross-audience contradiction AI analysis (not just headline diff)
- Narrative lifecycle classification (emerging/surging/peaked/declining/resurgent/faded/stable)
- Cyclic pattern detection (anniversary narratives — Victory Day, Tiananmen, etc.)
- Gradual audience targeting shift detection

### Grok Integration (Social Source Layer)
- Grok API for X/Twitter monitoring
- Gray source identification (accounts amplifying state media within 4hrs)
- Amplification network visualization
- Time-to-amplification tracking per narrative
- Confidence scoring for gray sources

### Additional Data Sources
- Telethon (Telegram) integration — Russian MoD, Rybar, WarGonzo, IRGC channels
- YouTube Data API — state media video channels (CGTN, RT, TRT World) with transcripts
- VK API — Russian domestic vs. export narrative comparison
- Weibo API — Chinese domestic vs. international narrative comparison

### Power User Features
- Custom watchlists with alerts (User Story #1: Capt Torres, #5: Sarah)
- Saved analyses / bookmarks (User Story #6: SPC Reeves)
- Per-journalist tracking within outlets (User Story #2: Marcus)
- Embeddable widgets for journalist articles (User Story #2, #4)
- Social sharing cards with rich previews per country page
- Team collaboration (comments, shared briefs) (User Story #1, #5)
- White-label / branded exports (User Story #5: Sarah)
- Downstream amplification tracking (state → mainstream social) (User Story #2)

### Monetization Activation (After Traction)
- Stripe billing integration ($10/month subscription)
- .mil email verification flow (free full access for military)
- Subscription paywall UI
- Account management (email, password, billing)
- Subscription metrics dashboard

### API Access (v2.0)
- Researcher API with usage-based pricing
- API documentation site (docs.salientsignal.com)
- API key management
- Rate limiting per tier
- Code examples and tutorials

### Expansion
- Outlet database 150 → 300 → 600+ (quarterly targets)
- Fine-grained monitoring of Tier 3 small nations
- Per-language activity tracking (not just per-country)
- Per-outlet activity dashboards
- Regional drill-downs on globe
- Custom theme taxonomy editor

---

## Critical Path

```
Phase 0 ──→ Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4 ──→ Phase 5 (14 days) ──→ Phase 8 ──→ Phase 9 (launch)
                                                                   │
                                                        Phase 6 + 7 run in parallel
```

**Longest chain:** ~3 weeks minimum from now to launch, assuming the pipeline runs cleanly for 14 days to build baselines.

**Fastest unblock:** Tasks 1-7 (Vercel 404 fix + Supabase URL) give you a working demo URL in under 10 minutes of your time.

**Parallelizable:** Phases 6 (UX Polish) and 7 (Content Pages) can run in parallel with Phase 5 (14-day baseline window) — perfect background agent work while the pipeline is accumulating data.

---

## Task Ownership Split — Claude Autonomous vs. Needs Don

> **67 of 100 tasks Claude can execute without Don's intervention.** 33 require Don because they involve third-party UI clicks, credentials, real-device testing, or passive waiting.

### ⚙️ Claude Autonomous (67 tasks)

**Phase 1 — Pipeline Code Review (all 10)**
Tasks 11-20. Read and validate every Python module from the background agent. Trace algorithm implementations against the spec, spot-check classifications, report findings.

**Phase 2 — Local Testing (7 of 10)**
- Task 21: Review schema.sql
- Task 25: Run seed_outlets.py (after schema initialized)
- Task 26: Run pipeline dry-run locally
- Task 27: Run live pipeline locally
- Task 28: Query Supabase to verify population
- Task 29: Spot-check 20 random classifications
- Task 30: Tune deviation thresholds

**Phase 4 — Frontend + Real Data (all 10)**
Tasks 41-50. Build Supabase client, all API routes, feature flag logic, update Globe and country components, loading/error states, flip the flag to real data.

**Phase 5 — Data Quality + Content (8 of 10)**
- Task 52: Build audit_classifications.py
- Task 53: Propose misclassification fixes
- Task 54: Build theme_labels.json
- Task 55: Update themes.py
- Task 56: Generate country_descriptions.json (write directly, no API cost)
- Task 57: Generate outlet_descriptions.json
- Task 58: Display country descriptions in UI
- Task 59: Display outlet descriptions in tooltips
- Task 60: Add "last updated" stale banner

**Phase 6 — UX Polish (all 10)**
Tasks 61-70. First-visit tutorial, tooltips, arc click modal, country search, mobile responsive audit + fixes, keyboard nav, screen reader support, reduced motion, globe perf optimization, Lighthouse audit.

**Phase 7 — Content Pages + Features (all 10)**
Tasks 71-80. Methodology, about, sources, FAQ, theme detail pages, country comparison, regional zoom, empty states, 404 page, keyboard shortcuts.

**Phase 8 — Pre-Launch Validation (6 of 10)**
- Task 81: Run 7 acceptance test cases
- Task 82: Edge case testing
- Task 85: Security audit (npm audit, secret scan)
- Task 86: Performance audit
- Task 87: Open Graph + Twitter card meta tags
- Task 88: Generate og-image.png
- Task 90: Sitemap, favicon, web manifest

**Phase 9 — Launch + Monitoring (4 of 10)**
- Task 94: Update internal references to new domain (after registration)
- Task 96: Add pipeline failure alert code
- Task 98: Fix bugs reported post-launch
- Task 99: Add 50 more outlets (150 → 200)

---

### 👤 Needs Don (33 tasks)

**Phase 0 — Infrastructure Setup (all 10)**
Tasks 1-10. All Vercel/Supabase/Render UI clicks or credentials Claude can't access.
- Check Vercel deployment status, verify production alias
- **Grab Supabase Project URL** (biggest blocker)
- Paste env vars into Vercel UI
- Create Render account, connect to GitHub
- Enable Vercel Analytics

**Phase 2 — Database Init (3 of 10)**
- Task 22: Run schema.sql in Supabase SQL Editor
- Task 23: Verify tables exist
- Task 24: Verify indices exist

*(Alternative: provide service role key + URL to execute SQL via REST API.)*

**Phase 3 — Render Cron Deployment (4 of 10)**
- Task 31: Create Render cron service (UI click)
- Task 32: Configure schedule `7 * * * *`
- Task 36: Trigger first manual cron run
- Task 40: Verify Render free tier usage

*(Tasks 33-35 can be pre-configured via `render.yaml` in the repo. Tasks 37-39 run autonomously.)*

**Phase 5 — Baseline Accumulation (1 of 10)**
- Task 51: Let pipeline run 14 days. Passive wait.

**Phase 8 — Real Device Testing + Accounts (3 of 10)**
- Task 83: Cross-browser testing (Safari, Firefox, Edge)
- Task 84: Real device testing (iPhone, iPad, Android)
- Task 89: Create Sentry account (Claude adds SDK afterward)

**Phase 9 — Domain + DNS + Monitoring (6 of 10)**
- Task 91: Register domain
- Task 92: Configure DNS records
- Task 93: Add custom domain to Vercel
- Task 95: Create UptimeRobot account + monitor
- Task 97: Weekly metrics review (read + discuss)
- Task 100: Month 1 retrospective decisions

---

### Unblock Priority for Don

Ordered by how much downstream work each of Don's actions unlocks:

1. **Get Supabase Project URL** (Task 4) → unlocks Phase 2-4 entirely (~30 autonomous tasks)
2. **Run schema.sql in Supabase** (Task 22) → unlocks Phase 2 testing
3. **Create Render cron service** (Task 31) → unlocks Phase 3 automation + Phase 5 baseline accumulation
4. **Verify Vercel deploy works** (Tasks 1-3) → live demo URL available
5. Everything else can wait until launch preparation

**Your minimum time investment before launch:** ~30 minutes of UI clicks across Supabase, Vercel, and Render. Plus the passive 14-day baseline window and an hour of real device testing at the end.

**Claude's autonomous workload:** 67 tasks can run via background agents while Don focuses on Apex primary activities (language study, fitness, Duke immersion, etc.).

---

## Budget Snapshot

| Phase | Expected Cost | Notes |
|-------|---------------|-------|
| Phases 0-4 | $0 | Free tiers only |
| Phase 5 content generation | ~$8 | One-time Claude API calls for descriptions |
| Phases 6-8 | $0 | Dev work |
| Phase 9 domain | ~$12-40/year | Domain registration |
| **MVP Total** | **~$20** | First year |

**Post-launch recurring:** $0/month until paid tier activates or volume forces Supabase Pro ($25/mo).

---

## Success Metrics (Week 1 After Launch)

- Zero pipeline failures / outages
- Baseline accuracy verified (spikes match real news events)
- Real GDELT data flowing correctly end-to-end
- Globe renders in <1s on mobile
- Lighthouse scores maintained (90+/95+/95+)
- Zero misclassification bugs that weren't caught in Phase 1-2 review
- Content pages (methodology, about, FAQ) ship without rework

---

## Related Files

- [[SalientSignal-Project]] — Product vision, design direction, monetization
- [[SalientSignal-Source-Database]] — 151+ countries, 606+ outlets, all APIs
- [[SalientSignal-Technical-Spec]] — Verified API limits, daily pipeline operations, costs
- [[SalientSignal-User-Stories]] — Six user archetypes, conversion triggers, feature gaps
- [[SalientSignal-Algorithms]] — Algorithm pseudocode + database schema
- Plan file: `/Users/don/.claude/plans/proud-jumping-key.md` — MVP implementation plan with 8 build phases

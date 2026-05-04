---
aliases:
  - SalientSignal
  - SalientSignal
tags:
  - apex
  - business
  - app
  - io
  - media-analysis
created: 2026-04-09
---

# SalientSignal

> **One-liner:** Foreign media intelligence briefs that let users see how state-run outlets frame, spin, and target narratives — without ever telling them what to think.

---

## Overview

| Field | Detail |
|-------|--------|
| **Entity** | Atlas Peak Media, LLC |
| **Platform** | Web (primary) — domain TBD (salientsignal.com or similar) |
| **Status** | Phase 0 COMPLETE — frontend scaffold deployed; Phase 1+2 (pipeline) in progress |
| **Codebase** | `/Users/don/Documents/Business/Atlas Peak Media, LLC/SalientSignal/` |
| **GitHub** | `AtlasPeakMedia/SalientSignal` (private) |
| **Vercel Project** | `salient-signal` under Atlas Peak Media team — `salient-signal.vercel.app` |
| **Supabase Project** | Created (project ref TBD — need URL from Don) |
| **Hosting** | Vercel Hobby (frontend) + Supabase Free (database) + Render Free (cron pipeline) = $0/month |
| **Revenue Model** | Free (today's data) / $10/mo (full archive + depth) / .mil = free full access |
| **API Dependencies** | GDELT (MVP), Claude (Phase 2), Grok (Phase 2), Telethon (Phase 2), YouTube (Phase 2) |
| **Countries Covered** | 151+ (every country with identifiable state media) |
| **Source Database** | 606+ state media outlets cataloged — see [[SalientSignal-Source-Database]] |
| **Initial Outlet Count** | 150 outlets at launch, expanding to 606+ |
| **Pre-Launch Blockers** | JAG/ethics review (active duty consideration), domain registration, 14 days of baseline data |
| **Target Launch** | After JAG clearance + 14-day pipeline validation |

---

## Build Status (as of 2026-04-09 evening)

### ✅ Phase 0 — Repo + Infrastructure Setup (COMPLETE)
- Repository created at `/Users/don/Documents/Business/Atlas Peak Media, LLC/SalientSignal/`
- Full directory structure scaffolded (`pipeline/`, `web/`, `shared/`, `.github/`, `docs/`)
- README.md, LICENSE, .gitignore created
- Git initialized, pushed to `AtlasPeakMedia/SalientSignal` (private)
- 2 commits to main: initial setup + Phase 0 frontend scaffold

### ✅ Phase 0.5 — Frontend Scaffold with Dummy Data (COMPLETE)
- **Stack:** Next.js 16 + React 19 + Tailwind CSS 3 + react-globe.gl + Three.js
- **20 files, 4,295 lines committed**
- Build verified: zero TypeScript errors, zero npm vulnerabilities
- Local dev server tested at `localhost:3456` — all routes return 200

**Frontend features built:**
- Interactive 3D globe with country polygon click handlers
- Natural Earth 110m country boundaries (819 KB GeoJSON)
- ~150 countries of dummy activity data with realistic baseline deviations
- View toggle: Domestic / International / Both
- Coordination arc lines (Russia-Venezuela-Cuba example, Iran-Syria-Yemen example)
- Country detail pages with side-by-side audience split (Domestic | International columns)
- Dummy headlines for Tier 1 countries in original languages (Russian, Chinese, Persian, Arabic, Spanish, English)
- Trending themes panel + biggest movers panel
- Dark theme with procedural grain texture (vFlat aesthetic per design spec)
- Empty states for unmonitored countries (Uruguay test passes)
- ISO_A2 fallback to ISO_A2_EH (Norway/France/Kosovo Natural Earth quirks)
- Mobile responsive layout

**Files in `web/`:**
```
web/
├── package.json (Next.js 16, React 19, react-globe.gl, three, tailwindcss)
├── next.config.ts (transpiles react-globe.gl, three)
├── tailwind.config.ts (full SalientSignal palette)
├── tsconfig.json
├── postcss.config.js
├── .env.example (env var template)
├── .env.local (gitignored — Supabase keys live here)
├── public/data/ne_110m_admin_0_countries.geojson (819 KB Natural Earth)
└── src/
    ├── app/
    │   ├── layout.tsx (dark theme shell with grain overlay)
    │   ├── page.tsx (globe home with movers/themes panels)
    │   └── country/[code]/page.tsx (audience split detail view)
    ├── components/
    │   ├── Globe/
    │   │   ├── GlobeWrapper.tsx (react-globe.gl wrapper, click handlers)
    │   │   ├── ViewToggle.tsx (Domestic/International/Both)
    │   │   └── ColorLegend.tsx (deviation color scale)
    │   └── Brand/
    │       └── Wordmark.tsx (SalientSignal logo)
    ├── lib/
    │   ├── dummy-data.ts (~150 countries, headlines, arcs, themes)
    │   └── colors.ts (deviation level → hex color mapping)
    └── styles/
        └── globals.css (grain texture, dark scrollbars, reduced motion)
```

### 🔄 Phase 0.6 — Vercel Deployment (IN PROGRESS)
- Vercel project `salient-signal` created under Atlas Peak Media team
- Connected to `AtlasPeakMedia/SalientSignal` GitHub repo
- Production URL: `salient-signal.vercel.app`
- Root Directory set to `web` (inside the repo)
- Environment variables added: `NEXT_PUBLIC_SUPABASE_URL` (placeholder), `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `NEXT_PUBLIC_USE_DUMMY_DATA=true`
- First deploy 404'd because root directory wasn't set before deploy
- Empty commit `97aaf3b` pushed to trigger fresh build with correct root directory
- **Status: Awaiting fresh build completion**

### 🔄 Phase 1 + Phase 2 — Source Classification + GDELT Pipeline (IN PROGRESS)
- Background agent launched 2026-04-09 evening
- Agent will build:
  - `pipeline/data/outlets.json` — initial 150 outlets with audience classification
  - `shared/countries.json` — FIPS↔ISO mapping for 195 countries
  - `pipeline/src/outlets.py` — outlet lookup functions
  - `pipeline/src/classifier.py` — Algorithm 1 (audience classification)
  - `pipeline/src/gdelt_client.py` — wraps `gdeltdoc` Python library
  - `pipeline/src/baselines.py` — Algorithm 2 (30-day rolling baselines)
  - `pipeline/src/deviation.py` — Algorithm 2 (ratio + z-score)
  - `pipeline/src/db.py` — Supabase Python client wrapper
  - `pipeline/src/coordination.py` — Algorithm 6 (cross-country narrative coordination)
  - `pipeline/src/themes.py` — GDELT GKG theme extraction
  - `pipeline/src/pipeline.py` — main orchestration
  - `shared/schema.sql` — Supabase tables (outlet_classification, articles, country_activity, coordination_events, daily_snapshots)
  - `pipeline/scripts/run_pipeline.py` — CLI for local testing
  - `pipeline/scripts/seed_outlets.py` — populates outlet table from JSON
  - Unit tests for all modules

### ⏳ Pending — Phase 3 (Render Cron Deployment)
- Render account created
- Cron job configuration not yet started (waits on Phase 1+2)

### ⏳ Pending — Phase 4 (Wire Frontend to Real Data)
- Replace dummy data with Supabase queries
- Feature flag `NEXT_PUBLIC_USE_DUMMY_DATA` toggles between dummy and real data
- Needs Supabase URL from Don

### ⏳ Pending — JAG/Ethics Review
- Same active-duty business ownership question as Loki and Atlas Peak Capital
- Blocks public launch (not development)
- Schedule alongside Loki + APC reviews

### ⏳ Pending — Domain Registration
- Defer until JAG sign-off
- Candidates: salientsignal.com, salientsignal.io, salientsignal.media (need to check availability)

---

---

## Product Vision

SalientSignal is a foreign media intelligence platform that monitors state-run and state-aligned news outlets, social media accounts, and gray-zone amplifier networks across adversary and competitor nations. It delivers analytical briefs — not labels, not scores, not warnings — that let users see what's being said, who it's being said to, how it differs across audiences, and what themes are emerging over time.

The app does NOT:
- Include US or Five Eyes (UK, Canada, Australia, New Zealand) media
- Explicitly name or display the SCAME framework
- Tell users what to think or label content as "propaganda"
- Rate outlets on a left-right political spectrum

The app DOES:
- Deliver debrief-style analytical paragraphs that naturally cover source attribution, content framing, audience targeting, media channel selection, and observable effects — without labeling any of those categories
- Track themes and messages across countries and regions over time
- Surface cross-audience contradictions (same country, same event, different narrative by language/region)
- Identify unaffiliated accounts that amplify state narratives (gray/black sources)
- Let users reach their own conclusions

---

## Analytical Framework (Internal Only)

> [!warning] Internal Reference
> SCAME is the analytical backbone but is NEVER exposed to users. All output is natural prose.

The Claude API prompt system produces debrief paragraphs that embed all five SCAME elements:

| SCAME Element | How It Appears in Output |
|---------------|--------------------------|
| **Source** | Named outlet, language desk, identified amplifier accounts |
| **Content** | What the piece says, how it frames the event, adjective/opinion vs. raw data |
| **Audience** | Which language feed, which regional outlet, which platform demographic |
| **Media** | Channel type (broadcast, social, print, Telegram), overt vs. covert distribution |
| **Effects** | Theme frequency trends, behavioral indicators, narrative adoption by non-state accounts |

**Example output:**

> RT's Spanish-language desk framed the summit as economic coercion of Eastern Europe — a theme that's appeared 47 times across Russian-aligned outlets this month, concentrated in Latin American and Southern European feeds. RT's English-language coverage of the same event emphasized security failures, while Sputnik Arabic highlighted civilian displacement. The narrative divergence suggests tailored messaging by region. Twelve unaffiliated accounts amplified the Spanish-language framing within 3 hours of publication.

---

## Target Countries & Source Categories

### Tier 1 — Primary Adversaries
| Country | Known State Media | State-Aligned | Social/Telegram |
|---------|-------------------|---------------|-----------------|
| **Russia** | RT (EN/ES/AR/FR/DE), TASS, RIA Novosti, Sputnik (multi-language), Rossiya 24, Izvestia | Tsargrad, Regnum, NewsFront, SouthFront | RT X accounts, Sputnik X, Telegram channels (Rybar, WarGonzo, Readovka) |
| **China (PRC)** | Xinhua, CGTN (EN/ES/AR/FR/RU), People's Daily, China Daily, Global Times, CRI | SCMP (partial), Caixin (partial), Guancha | X accounts, WeChat public accounts, YouTube channels, TikTok |
| **Iran** | Press TV, IRNA, Fars News, IRIB, Tehran Times | Al Alam, Al Mayadeen (aligned), Tasnim | Telegram channels, X accounts |
| **DPRK** | KCNA, Rodong Sinmun, Naenara, KCTV | Uriminzokkiri | Limited social presence |

### Tier 2 — Regional Powers / State-Influenced
| Country | Known State Media | Notes |
|---------|-------------------|-------|
| **Turkey** | TRT World, Anadolu Agency, Daily Sabah | NATO member but significant state media apparatus |
| **Qatar** | Al Jazeera (EN/AR), AJ+ | Editorially independent but state-funded |
| **Saudi Arabia** | Al Arabiya, SPA, Arab News | State-aligned, MBS editorial influence |
| **UAE** | WAM, The National, Sky News Arabia | State-aligned |
| **Venezuela** | TeleSUR, VTV | Maduro-aligned |
| **Cuba** | Granma, Prensa Latina | State-run |
| **Pakistan** | PTV, APP, Dawn (partial) | ISI influence on coverage |
| **Egypt** | Al-Ahram, MENA, CBC Egypt | State-aligned post-2013 |

### Tier 3 — Monitoring
| Country/Region | Examples |
|----------------|----------|
| **Belarus** | BelTA, Belarus 1 |
| **Syria** | SANA |
| **Myanmar** | MRTV, Global New Light of Myanmar |
| **Eritrea** | EriTV, Shabait |
| **Rwanda** | KT Press, New Times |
| **Ethiopia** | ENA, Fana Broadcasting |
| **Central Asia** | Akorda (KZ), UzA (UZ), Khovar (TJ) |

---

## Grok Integration — Source Discovery Engine

Grok's native X/Twitter access is the key differentiator for identifying **gray and black sources** that aren't officially labeled as state media.

### Discovery Tasks

1. **Known Account Monitoring**
   - Official state media X accounts (RT, Xinhua, CGTN, etc.)
   - Official government spokesperson accounts
   - State media journalist personal accounts

2. **Gray Source Identification**
   - Accounts that consistently amplify state narratives within hours of official publication
   - Accounts with coordinated posting patterns (same talking points, similar timing)
   - Accounts that shifted editorial direction in lockstep with known state outlets during specific events (e.g., accounts that flipped to pro-Russia framing post-Feb 2022)

3. **Network Mapping**
   - Identify amplification clusters (which accounts always share/quote the same sources)
   - Detect bot-like behavior patterns (posting cadence, language patterns, account age vs. activity)
   - Map cross-platform coordination (same narratives appearing on X, Telegram, YouTube within a window)

4. **Narrative Velocity Tracking**
   - Time-to-amplification: how quickly do gray accounts pick up state media narratives?
   - Which narratives get amplified vs. ignored?
   - Geographic clustering of amplifier accounts

### Grok API Usage

```
Grok API → Source discovery + X content ingestion + gray/black identification
           ↓
     Structured feed of identified content + source metadata
           ↓
     Claude API → SCAME analysis → Debrief paragraph generation
           ↓
     Theme/narrative tracking database
           ↓
     User-facing briefs
```

---

## Feature Set

### Core (v1.0)

**Daily Briefs**
- Morning brief: overnight developments across all monitored countries
- Regional briefs: by geographic area (Russia/Eurasia, PRC/Indo-Pacific, Iran/Middle East, etc.)
- Country briefs: deep dive on a single country's media output

**Narrative Tracker**
- Trending themes across state media (what topics are surging this week?)
- Theme frequency over time (line charts, no editorial labels)
- Cross-country theme correlation (are Russia and China running parallel narratives?)

**Cross-Audience Contradiction Detector**
- Same outlet, same event, different framing by language
- Side-by-side comparison view (e.g., RT English vs. RT Arabic on the same story)
- Historical contradiction log

**Source Profiles**
- Per-outlet profile: country, language desks, typical themes, audience reach
- Identified gray accounts with confidence scoring
- Amplification network visualizations

**Event View**
- Pick a global event → see how every monitored country's state media covered it
- Timeline of coverage emergence (who covered it first, how did framing evolve)
- Language-by-language comparison

### All Subscribers Get Everything (v1.x)

**Push Alerts**
- "Narrative surge" alerts when a theme spikes across multiple state outlets
- "New gray account" alerts when Grok identifies a previously unknown amplifier
- Country-specific watchlists

**Deep Dives**
- Long-form analytical pieces on major narratives (AI-generated, Claude-powered)
- Historical context: how this narrative has evolved over months/years
- Effectiveness indicators: did the narrative get picked up by non-state media?

**Historical Archive**
- Full daily archive — go back to any date and see that day's briefs
- Weekly/monthly rollup digests with top themes, biggest shifts, notable silences
- Trend explorer — theme frequency over time, cross-country correlation, audience targeting shifts
- "This day in state media" — anniversary patterns (Victory Day, Tiananmen, etc.)
- Time slider on globe — animate coverage patterns day by day through any date range
- Search across entire archive — "What did Iranian media say about Saudi Arabia in March 2027?"

**Export & Share**
- Export briefs as PDF
- Shareable narrative tracker links
- API access for researchers/journalists (v2.0+)

---

## Architecture

### Data Layer

```
┌──────────────────────────────────────────────────────────────┐
│                      DATA COLLECTION                          │
├──────────┬───────────┬──────────┬──────────┬────────────────┤
│ GDELT    │ RSS Feeds │ Grok API │ Telethon │ YouTube API    │
│ (FREE,   │ (direct   │ (X/Twitter│ (Telegram│ (transcripts,  │
│  100+    │  from     │  monitor │  channel │  state media   │
│  langs,  │  state    │  + gray  │  monitor │  channels)     │
│  15 min) │  media)   │  detect) │  Russia/ │                │
│          │           │          │  Iran)   │                │
└────┬─────┴─────┬─────┴────┬─────┴────┬─────┴───────┬────────┘
     └───────────┴──────────┴──────────┴─────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    PROCESSING PIPELINE                         │
│  Dedup → Language detect → Translate → Cluster                │
│  → Entity extraction → Theme classification                   │
│  Tools: Trafilatura (F1=0.945), Google Cloud Translation,     │
│         Scrapy+Playwright fallback                            │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                     ANALYSIS ENGINE                            │
│  Claude API: SCAME analysis → Debrief paragraph generation    │
│  Grok API: Source attribution + gray/black detection          │
│  Theme engine: Frequency, cross-country correlation, velocity │
│  Contradiction engine: Cross-language/audience comparison      │
│  Perspective API: Toxicity/manipulation scoring               │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                      DELIVERY LAYER                            │
│  iOS app │ Web app │ Push notifications │ Researcher API      │
└──────────────────────────────────────────────────────────────┘
```

### Tech Stack (Proposed)

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Backend** | Python (FastAPI) | Matches AURORA pipeline experience, async-native |
| **Database** | PostgreSQL + pgvector | Structured data + semantic search for narrative matching |
| **Cache** | Redis | Brief caching, rate limiting, real-time theme counts |
| **AI — Analysis** | Claude API (Sonnet for volume, Opus for deep dives) | Best analytical reasoning for nuanced debrief writing |
| **AI — Discovery** | Grok API (xAI) | Native X/Twitter access, real-time social monitoring |
| **AI — Translation** | Claude API | Multi-language content normalization |
| **Web (PRIMARY)** | Next.js + Globe.gl (Three.js) | Primary platform. Universal access. No install required. Globe.gl for interactive 3D globe with country polygon click handlers. |
| **iOS (FUTURE)** | Swift / SwiftUI + WKWebView globe | Optional future phase. WebView-wrapped Globe.gl for the globe. Native for notifications + offline reading. |
| **Hosting** | Railway or Fly.io | Cost-effective for pipeline + API serving |
| **Task Queue** | Celery + Redis | Scheduled collection runs, batch analysis |

---

## Design Direction

> **Reference:** vFlat splash screen aesthetic — dark background, noise grain texture, centered branding, minimal and premium. Intelligence feel without being try-hard military.

### Color Palette

| Element | Color | Hex (Approx) | Rationale |
|---------|-------|-------------|-----------|
| **Background** | Dark charcoal/near-black | `#0D0D0F` | Base surface. Grain texture overlay (3% density, 0.10-0.15 opacity). |
| **Globe ocean** | Dark navy | `#0A0F1A` | Barely lighter than background. Globe emerges subtly. |
| **Country polygon (neutral)** | Muted dark gray | `#1A1D24` | Quiet countries fade into the globe. |
| **Baseline spike (warm)** | Amber → Orange → Red | `#F5A623` → `#E8601C` → `#D93025` | Deviation from normal. Hotter = more anomalous. |
| **Baseline quiet (cool)** | Steel blue | `#4A7FB5` | Unusually silent. Silence can be a signal. |
| **Arc lines (coordination)** | Teal/cyan | `#00BFA5` | Connects countries pushing the same narrative. |
| **Brand accent** | Emerald teal | `#00897B` | Interactive elements, buttons, highlights, brand mark. |
| **Text (primary)** | White | `#FFFFFF` | Headlines, country names, brief titles. |
| **Text (secondary)** | Light gray | `#9E9E9E` | Metadata, timestamps, source attributions. |
| **Text (debrief body)** | Warm off-white | `#E0E0E0` | Long-form reading comfort against dark background. |
| **Cards/surfaces** | Elevated dark | `#161819` | Brief cards, country pages, modals. Subtle elevation via shadow. |
| **Dividers** | Subtle | `#2A2D32` | Hairline separators between sections. |

### Visual Principles

1. **Always dark.** No white screens, no light mode. The entire app stays dark. Briefs read like intelligence documents. Charts render in accent colors against dark surfaces. This is an app you open at night and it doesn't blast your eyes.

2. **Grain texture everywhere.** Procedural noise overlay on all background surfaces using the `GrainOverlay` SwiftUI component (Canvas-based, 3% density, 0.10-0.15 opacity, `.overlay` blend). Applies to splash, onboarding, globe view, brief backgrounds. Gives the "classified document" feel without fake military stamps.

3. **Globe as hero.** The 3D globe is the centerpiece — always visible, always interactive. Dark ocean, muted country polygons that light up based on baseline deviation. Arc lines glow like fiber optic traces across a dark map table. The globe sits against the grain-textured background like a situation room display.

4. **Minimal chrome.** No busy toolbars or tab bars cluttering the screen. Navigation is gestural where possible — swipe between briefs, tap countries on globe, pull up search. When UI elements appear they should feel like they're emerging from the dark surface, not sitting on top of it.

5. **Typography.** Clean sans-serif. Body text in warm off-white for reading comfort. Headlines in pure white. Monospaced for data points (article counts, percentages, timestamps). Dynamic Type throughout.

6. **Data visualization.** Charts use the accent palette against dark backgrounds. Line charts for theme frequency. Heatmaps for country activity. No 3D chart effects, no gradients on bars. Flat, precise, readable.

7. **Animations.** Subtle spring animations. Globe rotation is slow and smooth. Country highlights fade in, don't snap. Arc lines animate along their path like data flowing between nodes. Respect `accessibilityReduceMotion`.

8. **The silence signal.** Countries that go unusually quiet glow cool blue. This is a deliberate design choice — most apps only highlight activity. SalientSignal highlights absence. A country going dark is information.

### Key Screens

**Splash** — Dark grain background, centered "SalientSignal" logotype + icon. Identical vFlat energy. Holds for 1.5s then transitions to globe.

**Globe (Home)** — Full-screen interactive globe against grain background. Minimal HUD: search icon top-left, filter icon top-right, date/time slider at bottom. Countries colored by baseline deviation. Arc lines for detected coordination. Tap any country to enter.

**Country Page** — Slides up from globe tap. Dark card surface. Country name + flag + activity indicator. Today's brief (debrief paragraphs). Active themes (ranked pills with frequency badges). Outlet list. Gray account section. Contradiction log. Historical calendar. All scrollable.

**Brief View** — Full debrief paragraph text against dark background. Source citations inline. Tappable theme tags. Timestamp and confidence indicators in secondary text. Share button.

**Trend Explorer** — Dark chart view. Theme frequency over time. Country comparison overlays. Time range selector. The globe sits as a small reference in the corner showing geographic distribution of the selected theme.

**Weekly/Monthly Digest** — Card-based summary. Top themes ranked with delta indicators (up/down vs. prior period). Biggest spikes. Notable silences. New gray accounts. Shareable as PDF.

### App Icon Direction

Dark background (matching app surface). Globe silhouette or abstract globe wireframe in teal/emerald accent. Clean, recognizable at small sizes. No text in the icon.

---

### Cost Model

> [!note] This app has operational costs — unlike zero-cost iOS apps in the APM portfolio.

| Component | Estimated Monthly Cost | Notes |
|-----------|----------------------|-------|
| Claude API (Sonnet) | $50-200 | Batch SCAME analysis, ~5,000-20,000 articles/month |
| Claude API (Opus) | $20-50 | Deep dive pieces, ~100-500/month |
| Grok API | $50-150 | X monitoring, source discovery |
| Hosting (Railway) | $20-50 | Backend + DB + Redis |
| RSS feeds | $0 | Public feeds, no licensing |
| **Total** | **$140-450/month** | Scales with article volume |

Break-even at ~50-150 subscribers depending on pricing tier.

---

## Monetization

**Three tiers. Free tier provides real value. Paid unlocks the archive and depth.**

| Tier | Price | Access |
|------|-------|--------|
| **Free** | **$0** | Interactive globe, today's morning brief (top stories across all countries), country pages with current-day data, baseline deviation coloring, coordination arc lines. Enough to see what's happening right now. |
| **Full Access** | **$10/month** | Everything in Free + complete historical archive (every day since launch), trend explorer with time slider, weekly/monthly rollup digests, cross-audience contradiction log, deep dives, push alerts, country watchlists, full-text search across archive, PDF export. |
| **.mil (Military)** | **Free** | Full Access tier. Verified via .mil email. |
| **API** (v2.0) | Usage-based | Programmatic access for researchers, journalists, think tanks. Future phase. |

### Why This Split Works

The analysis pipeline generates briefs once and serves them to everyone. The marginal cost of a free user reading today's brief is near zero — the brief already exists. Free users see the globe, understand the product, and convert when they want to look back in time. The historical archive is the paywall trigger: *I want to see what this looked like last month* is the conversion moment.

### .mil Verification

Users sign up with a .mil email address → receive a confirmation link → click to verify → account permanently flagged as military, Full Access granted at no cost.

Eligible domains:
- `.mil` — US military (all branches, DoD civilians, some contractors)
- Future consideration: `.gov`, allied military domains (`.mod.uk`, `.forces.gc.ca`, etc.), `.edu` (academic researchers)

Military users are the highest-value audience — they validate the product to their networks and are most likely to share it within the defense community.

### Revenue Math

| Paid Subscribers | Monthly Revenue | Monthly Cost (est.) | Net |
|-----------------|-----------------|--------------------|----|
| 100 | $1,000 | $300-500 | $500-700 |
| 500 | $5,000 | $600-1,000 | $4,000-4,400 |
| 1,000 | $10,000 | $800-1,500 | $8,500-9,200 |
| 5,000 | $50,000 | $2,000-4,000 | $46,000-48,000 |

Costs scale sublinearly — the pipeline runs regardless of user count. More users don't mean more GDELT queries or more Claude analysis. The fixed cost is the analysis pipeline (~$200-450/mo at MVP). Free users cost near zero to serve.

---

## Competitive Landscape

| Product | What It Does | What SalientSignal Does Differently |
|---------|-------------|--------------------------------------|
| **Ground News** | Rates news bias on L-R spectrum, shows coverage gaps | Domestic focus. No state media analysis, no SCAME, no cross-audience detection |
| **AllSides** | L-R bias ratings for US outlets | US-only. No foreign state media |
| **Ad Fontes Media** | Media bias chart | Static ratings. No dynamic analysis, no foreign media |
| **Hamilton 2.0 (ASD)** | Tracked Russian/Chinese/Iranian state media | **Shut down 2023.** SalientSignal fills this exact vacuum |
| **EUvsDisinfo** | EU database of pro-Kremlin disinformation | Russia-only. Database format, not briefs. No real-time analysis |
| **Bellingcat** | OSINT investigations | Manual, investigative, not automated daily briefs |
| **NewsGuard** | Trust ratings for news websites | Ratings-based, no analytical briefs, no theme tracking |

**Key gap:** Hamilton 2.0 (Alliance for Securing Democracy) was the closest thing to this and it shut down in 2023. The GEC was defunded. There is NO public-facing tool that does automated foreign state media analysis for general audiences.

---

## Legal & Ethics Considerations

- [ ] **JAG/Ethics review** — Same active-duty business ownership question as Loki. Does analyzing foreign state media create any conflict with official duties as 1707?
- [ ] **No classified sources** — ALL inputs are open source (RSS, public X accounts, public Telegram). Zero classified material.
- [ ] **No US/FVEY analysis** — Hard constraint. Never analyze allied media. Build this into the system architecture (country exclusion list), not just policy.
- [ ] **First Amendment** — Analyzing publicly available foreign media is protected speech
- [ ] **Terms of Service** — Ensure Grok API and X API usage complies with ToS for automated monitoring
- [ ] **FARA considerations** — App must NOT be fundable by or affiliated with any foreign government. Revenue is purely commercial subscriptions.
- [ ] **Translation attribution** — When translating foreign-language content, note it was machine-translated

---

## Apex Integration

| Phase | SalientSignal Activity |
|-------|--------------------------|
| **Phase 1 (Months 1-6)** | Concept, market research, architecture design. No coding — focus on Apex core. |
| **Phase 2 (Months 7-12)** | Backend pipeline build (Claude Code background agents). Feed database, processing pipeline, Claude SCAME prompts. |
| **Phase 3 (Months 13-18)** | iOS + web build. Grok integration. Beta testing. |
| **Post-Apex** | Launch, iterate, scale. Potential think tank partnerships (CSIS, Brookings, RAND). |

---

## Development Gameplan

### Phase A — Research & Design
- [x] Compile complete state media source database — **DONE** (151+ countries, 606+ outlets, 7 API tiers, discovery methods). See [[SalientSignal-Source-Database]]
- [ ] Populate RSS feed URLs, X handles, YouTube channel IDs, Telegram links for every outlet in database
- [ ] Design Claude SCAME prompt templates that produce natural debrief prose
- [ ] Design Grok source discovery prompt templates
- [ ] Define theme taxonomy (what categories of narratives to track)
- [ ] Wireframe iOS app (brief view, narrative tracker, event view, source profiles)
- [ ] Wireframe web companion

### Phase B — Backend Pipeline
- [ ] RSS collection engine (country-tagged, language-tagged)
- [ ] Grok API integration (X monitoring + gray source discovery)
- [ ] Translation pipeline (Claude API, normalize all content to English)
- [ ] Dedup and clustering engine
- [ ] Claude SCAME analysis engine (structured JSON → debrief paragraph)
- [ ] Theme extraction and frequency tracking
- [ ] Cross-audience contradiction detection
- [ ] PostgreSQL schema (sources, articles, analyses, themes, contradictions)
- [ ] Brief generation engine (morning, regional, country, event)
- [ ] API endpoints for iOS/web consumption

### Phase C — Web App (PRIMARY PLATFORM)
- [ ] Globe home screen (Globe.gl + Three.js, Natural Earth GeoJSON, country polygon click handlers)
- [ ] Country pages (brief, themes, outlets, gray accounts, contradictions, history)
- [ ] Brief feed (scrollable daily briefs with debrief paragraphs)
- [ ] Narrative tracker (theme frequency charts, cross-country correlation)
- [ ] Trend explorer (time-range selector, theme comparison, globe time slider)
- [ ] Event view (multi-country coverage comparison, timeline of emergence)
- [ ] Cross-audience contradiction view (side-by-side language desk comparison)
- [ ] Source profiles (outlet detail, gray account confidence scores, amplification network viz)
- [ ] Historical archive (calendar view, weekly/monthly digests, full-text search)
- [ ] Baseline deviation color system (30-day rolling average per country/outlet/theme)
- [ ] Arc line visualization (cross-country narrative coordination)
- [ ] Dark theme with grain texture (Next.js + Tailwind, no light mode)
- [ ] Authentication (email + password, email verification)
- [ ] .mil email verification (free access for verified military accounts)
- [ ] Stripe subscription ($10/month)
- [ ] Email push alerts (narrative surges, new gray accounts, country watchlists)
- [ ] PDF export for briefs and digests
- [ ] Mobile responsive (the globe and all views must work on phone browsers)

### Phase D — iOS App (FUTURE, OPTIONAL)
- [ ] WKWebView-wrapped Globe.gl for interactive globe
- [ ] Native push notifications
- [ ] Offline reading (cached briefs)
- [ ] Subscription via StoreKit 2 (or direct to web billing)

### Phase E — Launch
- [ ] Marketing: target .mil community (word of mouth through free accounts), OSINT community, IR/PoliSci academics, journalists
- [ ] Think tank outreach (CSIS, Brookings, RAND, Atlantic Council)
- [ ] Academic partnerships (university IR/PoliSci departments)
- [ ] Researcher API (v2.0 — usage-based pricing for programmatic access)

---

## Open Questions

- [x] **Platform priority:** RESOLVED — Web-first (Next.js + Globe.gl). iOS future/optional. Maximum reach, no install required, works on .mil networks.
- [x] **Grok API pricing:** RESOLVED — Grok 4.1 Fast: $0.20/$0.50 per M tokens. X Search: $5/1,000 calls. Very affordable.
- [ ] **Content moderation:** If gray accounts post genuinely harmful content, how to handle display?
- [ ] **Update cadence:** How often to refresh analysis? Hourly? Every 6 hours? Daily batch?
- [ ] **Historical depth:** How far back to load on launch? 30 days? 90 days? 1 year? (GDELT goes back to 1979)
- [ ] **Partnerships:** Approach think tanks pre-launch for credibility + distribution?
- [ ] **VK/Weibo access:** VK API requires Russian-language auth flow. Weibo API requires Chinese registration. Need proxy strategy for domestic narrative comparison feature.
- [ ] **JAG review:** Same active-duty business ownership question as Loki. Schedule alongside Loki JAG consultation.

---

## Related Files

- [[SalientSignal-Way-Ahead]] — **100-task roadmap from here through launch** (phases 0-9 with dependencies)
- [[SalientSignal-Source-Database]] — Master source database: 151+ countries, 606+ outlets, all APIs, discovery methods
- [[SalientSignal-Technical-Spec]] — Verified API limits, daily pipeline operations, costs
- [[SalientSignal-User-Stories]] — Six user archetypes, conversion triggers, feature gaps
- [[SalientSignal-Algorithms]] — Algorithm pseudocode + database schema
- [[Atlas-Peak-Media]] — Parent company portfolio
- [[iOS-Premium-Design-Reference]] — iOS design standards (applies to web too)
- [[iOS-Design-Implementation-Plan]] — Cross-app implementation plan
- [[App-Design/App-Master-Todo]] — Portfolio-wide task tracking

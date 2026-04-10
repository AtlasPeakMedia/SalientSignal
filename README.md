# SalientSignal

> Foreign media intelligence. Every country's state media on a globe. Sentiment surfaces. Patterns emerge.

A web-based foreign media intelligence platform that monitors state-run and state-aligned media from 151+ countries. Visualizes daily activity on an interactive 3D globe, splits domestic vs. international messaging, and surfaces narrative coordination across regimes.

US and Five Eyes media are not analyzed. The product focuses exclusively on adversary and competitor state messaging.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Render Free Cron                               │
│  Python pipeline runs hourly                    │
│  - Queries GDELT for monitored country domains  │
│  - Classifies articles by audience              │
│  - Calculates baseline deviations               │
│  - Detects coordination patterns                │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│  Supabase (Free tier)                           │
│  - PostgreSQL: articles, snapshots, baselines   │
│  - Auth (.mil verification when added)          │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│  Vercel (Hobby tier)                            │
│  - Next.js 15 + React 19                        │
│  - Globe.gl for interactive 3D globe            │
└─────────────────────────────────────────────────┘
```

---

## Repository Layout

```
SalientSignal/
├── pipeline/         # Python data pipeline (Render cron)
│   ├── src/          # Source code
│   ├── data/         # Outlet classification, theme labels
│   ├── tests/        # Unit tests
│   └── scripts/      # CLI tools, manual runs
├── web/              # Next.js 15 web app (Vercel)
│   ├── src/          # Source code
│   ├── public/       # Static assets, GeoJSON
│   └── tests/        # Component tests
├── shared/           # Schemas, country data, outlet data
├── .github/          # CI workflows
└── docs/             # Architecture, deployment, algorithms
```

---

## Status

**Phase 0** — Repository setup and infrastructure provisioning. Not yet functional.

See [Project Apex vault](../../../Library/Mobile%20Documents/iCloud~md~obsidian/Documents/Project%20Apex/Business/SalientSignal/) for full specifications:
- `SalientSignal-Project.md` — product vision, design, monetization
- `SalientSignal-Source-Database.md` — 606+ outlets, 151+ countries, all APIs
- `SalientSignal-Technical-Spec.md` — verified API limits, daily pipeline, costs
- `SalientSignal-User-Stories.md` — six user archetypes, conversion triggers
- `SalientSignal-Algorithms.md` — algorithm specifications and database schema

---

## License

Proprietary. All rights reserved. Atlas Peak Media, LLC.

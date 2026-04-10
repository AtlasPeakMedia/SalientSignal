# Cold Start — What to Expect in the First 21 Days

> **Short version:** The globe will look muted for about a week and partially
> calibrated for three weeks. That's by design, not a bug. Read this before
> assuming something is broken.

## The Problem Cold Start Creates

SalientSignal's core signal is **deviation from a country's own baseline**.
Each country is compared against its own 30-day rolling average of state media
output. Red/orange/amber means "this country is publishing noticeably more
than usual." Blue/gray means "this country is quieter than usual."

Before the pipeline has run for 30 days, there is no baseline to deviate from.
So for the first few weeks, every country looks "normal" by default even if
something interesting is actually happening.

Without explicit handling, the globe would sit gray-neutral for a week, then
occasionally light up with low-confidence anomalies that the anti-hallucination
agent would suppress on MEDIUM or LOW confidence — making the whole product
look dead.

## How The Pipeline Handles Cold Start

The Anti-Hallucination Agent (`src/antihal.py`) recognizes three calibration
phases based on `days_sampled` from `fetch_baseline()`:

| Phase          | Days         | Baseline Confidence | Behavior                                                      |
|----------------|--------------|---------------------|---------------------------------------------------------------|
| **Cold start** | 1 – 6 days   | `LOW` (effectively 0) | Publish ALL levels with calibration caveat. `cold_start=true` in the row. |
| **Warming up** | 7 – 20 days  | `MEDIUM`            | Publish normally. Extreme levels (red/deepBlue) get a "warming up" caveat. `cold_start=true`. |
| **Stable**     | 21+ days     | `HIGH`              | Normal path. Extreme levels with LOW baseline confidence get suppressed. |

### Database signal: `cold_start` column

`country_activity.cold_start` is a boolean. When `true`, the frontend should
render a small banner or badge on that country's view explaining that the
baseline is still calibrating.

### Visual messaging for operators

When you first boot the pipeline, the globe will look like this progression:

**Day 1:**
- Globe colors based on the ratio ONLY (no z-score because std is meaningless
  with 0 days of baseline).
- Every country row has `cold_start=true` and a caveat: `"Calibrating baseline
  (0/7 days) — signals will stabilize after one week of continuous data collection."`
- This is NORMAL.

**Day 3–6:**
- Baseline has a handful of data points but not enough for a reliable std.
- Ratio-based coloring keeps working.
- `cold_start=true` banner still present.

**Day 7:**
- Baseline confidence promotes to `MEDIUM`.
- Caveat shifts to: `"Baseline warming up (7/21 days) — extreme anomaly claims need longer calibration period."`
- Red/deepBlue claims now publish but with a visible caveat.
- Coordination events can start firing but the anti-hal agent is still
  aggressive about suppression.

**Day 21:**
- Baseline confidence is `HIGH`.
- `cold_start=false` for all rows.
- Globe shows full-fidelity signals.
- Coordination arcs no longer get automatic Phase A caveats for warming-up
  reasons (they still have the standard "validate manually" caveat until
  Phase B is deployed).

## Operational Implications

### If you see a flat-gray globe after 72 hours

Check `pipeline_runs`:
```sql
SELECT started_at_utc, outcome, elapsed_seconds, stats
FROM pipeline_runs
ORDER BY started_at_utc DESC
LIMIT 10;
```

If `outcome != 'SUCCESS'` on recent rows, the pipeline is failing to write
and you need to investigate before worrying about cold start.

If rows are being written but `stats.articles_inserted` is 0, GDELT is
returning empty DataFrames — run `python scripts/gdelt_probe.py --country=RU`
to diagnose.

### If you see a dead globe after 7 days

Check the baselines:
```sql
SELECT country, audience_type, COUNT(*) AS day_count
FROM articles
WHERE pub_date >= NOW() - INTERVAL '7 days'
GROUP BY country, audience_type
ORDER BY day_count DESC
LIMIT 20;
```

If Tier 1 countries (RU, CN, IR, KP) are returning fewer than ~10 articles per
day, the classifier is under-recognizing outlets — run the verification
scripts:
```bash
python scripts/verify_seed.py
python scripts/verify_first_run.py --countries=RU,CN,IR,KP
```

### If baselines look wrong after Day 21

Possible causes:
1. **GDELT outage during warm-up:** a 5-hour GDELT outage looks like "all
   countries went silent for 5 hours" to the baseline computation. Permanently
   skews the mean down. Fix: manually purge the affected `articles` rows, let
   the baseline recompute. Phase C work adds automatic outage detection.
2. **Wrong classification boundary:** outlet classification moved an outlet
   from DOMESTIC to INTERNATIONAL (or vice versa) mid-warm-up. Each audience
   bucket now has a distorted history. Fix: re-run the classifier on the
   affected articles after updating `outlets.json`.
3. **Day-of-week effect:** the pipeline currently uses an unsegmented 30-day
   average, so weekends vs weekdays pool together. A country that publishes
   heavily on weekdays and lightly on weekends will show false red on
   weekdays and false blue on weekends. This is a known limitation —
   Phase B will add day-of-week baseline segmentation.

## Frontend Messaging

When `cold_start = true`, the frontend should show a small non-dismissible
banner with these exact phrases:

**Cold start (days 1–6):**
> Calibrating baseline — signals will stabilize in the first week of continuous
> data collection. Low statistical confidence during this period.

**Warming up (days 7–20):**
> Baseline warming up — coordination and extreme-anomaly signals may be
> under-calibrated. Full statistical confidence after three weeks.

**Stable (day 21+):**
> No banner. Normal product experience.

## Operational Checklist for Cold Start

Before the first live run:
- [ ] Schema verified (`verify_schema.py` passes)
- [ ] Outlets seeded and verified (`verify_seed.py` passes)
- [ ] GDELT probed (`gdelt_probe.py --country=RU` shows >30% outlet match rate)
- [ ] First live run on Tier 1 only (RU, CN, IR, KP)
- [ ] `verify_first_run.py` passes
- [ ] Operator knows NOT to panic about the gray globe on Day 1

During warm-up:
- [ ] Daily check of `pipeline_runs` outcome (should be SUCCESS every hour)
- [ ] Daily spot-check of 20 random article classifications
- [ ] Weekly review of `analysis_suppressed` to understand what anti-hal is killing
- [ ] Day 7 check: confirm `cold_start=false` starts appearing for high-volume
      countries (those with consistent daily data)

After warm-up:
- [ ] Day 21 check: full globe should be live, all `cold_start=false`
- [ ] Review coordination events for any obvious false positives (anti-hal
      should have caught most of them)
- [ ] Compare baselines between Tier 1 countries for sanity
      (e.g., Russia should have more articles than Belarus)

---

Cold start is a known and expected phase of a baseline-driven system. The
pipeline is designed to give operators and users a clear signal that the
system is calibrating rather than hiding that fact behind a broken-looking
globe. Three weeks of patience is a non-negotiable part of the product.

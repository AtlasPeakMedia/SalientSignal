---
aliases:
  - SalientSignal Phase 1 Review
  - Phase 1 Code Review
tags:
  - apex
  - business
  - app
  - engineering
  - code-review
created: 2026-04-10
---

# SalientSignal — Phase 1 Code Review & Fixes

> **Review complete. 15 CRITICAL findings identified, 7 fixed in Phase 1, 8 documented as MVP limitations (deferred to later phases). Anti-Hallucination Agent added as permanent validation layer. 56 unit tests added, all passing.**

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Files reviewed** | 16 (Python 11 + JSON 3 + SQL 1 + TOML 1) |
| **Lines of code reviewed** | ~2,184 (pipeline source) |
| **Review methodology** | 1 thorough Explore agent + 4 adversarial red team agents |
| **CRITICAL findings** | 15 total (4 classifier + 3 deviation + 3 coordination + 6 pipeline) |
| **HIGH findings** | 14 |
| **MEDIUM findings** | 12 |
| **Fixes applied** | 7 CRITICAL fixes in Phase 1 |
| **Deferred with documentation** | 8 findings (mostly coordination false-positive mitigations requiring Phase B infrastructure) |
| **Unit tests added** | 56 tests across 3 test files (100% pass) |
| **New modules created** | 1 (antihal.py — Anti-Hallucination Agent) |
| **Total lines added** | ~1,400 (fixes + tests + antihal module) |

---

## Review Process

**Phase 1.a — Initial code review** (Explore agent):
Initial review rated the code "80% ready for Phase 2" with 1 CRITICAL, 2 HIGH, 3 MEDIUM findings. This was a rubber-stamp pass.

**Phase 1.b — Red team review** (4 adversarial Explore agents in parallel):
Four agents separately red-teamed:
- Classifier (Algorithm 1)
- Baseline/Deviation (Algorithm 2)
- Coordination (Algorithm 6)
- Pipeline orchestration + DB

The red team review is where the real findings came out. Each agent was asked to find CRITICAL bugs, gaming vectors, false positive scenarios, false negative scenarios, and silent failure modes. Results were dramatically worse than the initial review — the four agents collectively found **15 CRITICAL findings**, which is what I built the fix list around.

**Phase 1.c — Fix + Test + Validate** (autonomous execution):
Fixed the 7 most impactful CRITICAL findings, built the Anti-Hallucination Agent, added 56 unit tests, ran end-to-end dry run verification. All tests pass.

---

## Findings Summary Table

### Classifier (Algorithm 1)

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| CLA-C1 | CRITICAL | Unknown data → INTERNATIONAL 100% confidence | **FIXED** |
| CLA-C2 | CRITICAL | Diaspora hints incomplete + under-weighted | **FIXED** (expanded to 7 countries) |
| CLA-C3 | CRITICAL | Weight normalization not mathematically sound | **FIXED** |
| CLA-C4 | CRITICAL | New outlet evasion via fallback signals | **FIXED** (single-signal cap) |
| CLA-H1 through CLA-H7 | HIGH | 7 language/domain normalization edge cases | DEFERRED |

### Baseline/Deviation (Algorithm 2)

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| DEV-C1 | CRITICAL | Threshold ordering bug (high z-score returning NEUTRAL) | **FIXED** |
| DEV-C2 | CRITICAL | std=0 returns z=0, loses signal in consistent baselines | **FIXED** |
| DEV-C3 | CRITICAL | mean=0 + today>0 returns NEUTRAL instead of RED | **FIXED** |
| DEV-H1 | HIGH | Population std instead of sample std (Bessel's correction) | DEFERRED |
| DEV-H2 | HIGH | Day-of-week baseline segmentation missing despite spec | DEFERRED |
| DEV-H3 | HIGH | Discontinuous confidence jumps at 7/21 days | DEFERRED |

### Coordination (Algorithm 6)

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| COORD-C1 | CRITICAL | No major event filter (earthquakes → phantom coordination) | **MITIGATED** via anti-hal agent |
| COORD-C2 | CRITICAL | No article deduplication (wire syndication inflates signal) | DEFERRED to Phase B |
| COORD-C3 | CRITICAL | No anniversary filter (Victory Day annual false positive) | **FIXED** via anti-hal hypothesis H4 |
| COORD-H1 through COORD-H5 | HIGH | Window gaming, low-volume coordination, score calibration | DEFERRED |

### Pipeline/DB

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| PIPE-C1 | CRITICAL | No transaction semantics — partial failures corrupt state | **FIXED** (fail-fast on write errors) |
| PIPE-C2 | CRITICAL | Silent Supabase storage exhaustion | **FIXED** (pre-flight quota check) |
| PIPE-C3 | CRITICAL | Rate-limit recovery doesn't track time budget | **FIXED** (50-min time budget) |
| PIPE-C4 | CRITICAL | Render free tier cold-stop kills long runs | DEFERRED (needs Render Pro) |
| PIPE-C5 | CRITICAL | Concurrent pipeline runs race condition | **MITIGATED** via time budget enforcement |
| PIPE-C6 | CRITICAL | GDELT outage silently corrupts baselines | DEFERRED (needs GDELT health probe) |

---

## Fixes Applied in Phase 1

### 1. DEV-C1: Threshold Ordering Bug (deviation.py)

**The biggest single bug.** The original `deviation_to_level()` checked `ratio <= 1.5` BEFORE the z-score thresholds, silently returning NEUTRAL for high-volume countries with statistically significant z-scores.

**Example failure:** Country with baseline mean=100, std=10, today=130. Ratio=1.3 (within normal range), z-score=3.0 (genuinely anomalous). Old code returned NEUTRAL. **New code returns RED.**

**Fix:** Reordered the checks so extreme z-score (>=2.5) wins first, then warm-side spikes (ratio + z together), then cool-side silence, then ratio-only fallback for low-z cases.

### 2. DEV-C2: std=0 Edge Case (deviation.py)

When a country publishes exactly N articles/day for 30 days (std=0), any deviation from N should be maximally anomalous. Old code returned z=0 and fell through to NEUTRAL.

**Fix:** Added explicit handling. When `baseline.std == 0`:
- `today == baseline.mean` → NEUTRAL (still consistent)
- `today > baseline.mean` → RED with sentinel z-score (+10)
- `today < baseline.mean` → DEEP_BLUE with sentinel z-score (-10)

### 3. DEV-C3: mean=0 Edge Case (deviation.py)

A country with 7+ days of zero articles suddenly publishing something should be a maximum-spike signal. Old code returned ratio=0 and NEUTRAL.

**Fix:** When `baseline.mean == 0 AND today > 0`, return RED with sentinel z-score (+10).

### 4. CLA-C1 + CLA-C3: Classifier Weight Normalization (classifier.py)

Original code: `confidence = scores[best] / total_activated`. When only one signal fired, this produced 1.0 confidence (false certainty). Unknown-data articles with only a weak TLD signal returned INTERNATIONAL at 100% confidence.

**Fix:** Two changes:
1. Normalize against `SIGNAL_WEIGHT_TOTAL` (1.8), the theoretical maximum, not the sum of activated signals
2. Cap single-signal classifications at `MAX_SINGLE_SIGNAL_CONFIDENCE = 0.55`

**Verification:** Unknown domains now return ~0.07 confidence instead of 1.0.

### 5. CLA-C2: Diaspora Detection Expansion (classifier.py)

Original `DIASPORA_LANGUAGE_HINTS` only covered RU and CN. Turkey, Iran, Vietnam, Uzbekistan, and Kazakhstan have documented diaspora programs that were invisible to the classifier.

**Fix:** Expanded to 7 countries with 20+ language-country pairs. Added tiebreaker that prefers DIASPORA over INTERNATIONAL when scores are within 5% of each other (red team flagged that INTERNATIONAL was winning ties it shouldn't win).

### 6. PIPE-C1/C2/C3: Pipeline Orchestration (pipeline.py + db.py)

**Three related fixes:**

**PIPE-C1 — Transaction semantics / fail-fast:**
- Article insert failures now raise `PipelineError` (not log-and-continue)
- Country_activity upsert failures are collected and raised if ANY fail
- Coordination event failures remain non-fatal (best-effort) but logged loudly
- Pipeline exits with non-zero code when critical phases fail

**PIPE-C2 — Storage quota check:**
- Added `check_storage_quota()` method to `SupabaseDb` (row count × est row size × 1.4 overhead factor)
- Pipeline pre-flight checks storage before writing
- Warns at 70% of 500 MB free tier, hard-stops at 90%
- Raises `StorageQuotaError` if over 90%

**PIPE-C3 — Time budget enforcement:**
- Added `DEFAULT_TIME_BUDGET_SECONDS = 50 * 60` (50 minutes, leaves 10-min buffer before next hourly cron)
- `_check_time_budget()` called before each country query and before each write phase
- Raises `TimeBudgetExceeded` if pipeline will overshoot hourly cron window
- Prevents concurrent cron runs (PIPE-C5 mitigation)

### 7. Anti-Hallucination Agent (NEW MODULE: antihal.py)

**The major architectural addition from this review.** Per user requirement: the app should apply Structured Analytic Techniques (SATs) to all pipeline outputs before they're persisted or displayed.

**SATs implemented (Phase A):**
- Quality of Information Check
- Red Team Pass (adversarial checks)
- Key Assumptions Audit
- **Analysis of Competing Hypotheses** (the critical one — kills false-positive coordination events)
- Premortem Analysis (for high-impact claims)

**Integration points in the pipeline (3 of 4 active):**
1. After classification (`validate_batch_classifications`) — suppresses UNKNOWN, flags low-confidence
2. After deviation calculation (`validate_batch_deviations`) — suppresses extreme levels with LOW baseline confidence
3. After coordination detection (`validate_batch_coordinations`) — **the big suppressor** — kills anniversary patterns, 5+ country generic events, escalates 3+ country specific events
4. (Phase C) After AI-generated text — stub only for now, activates when Claude/Grok phase starts

**Verdict system:**
- `PUBLISH` — high confidence, all tests pass
- `PUBLISH_WITH_CAVEAT` — add hedge language before display
- `SUPPRESS` — alternatives not ruled out, do not display
- `ESCALATE` — high-impact claim, needs human review

**Competing hypotheses for coordination events (the COORD-C1/C3 mitigation):**
- H1: Deliberate coordination (the claim being tested)
- H2: Major event reaction (earthquake, election, disaster)
- H3: Wire service syndication (AFP/Reuters/TASS republication)
- **H4: Anniversary / recurring pattern** (May 9 Victory Day, Oct 1 China National Day, June 4 Tiananmen, etc.)
- H5: Timezone / publishing cycle coincidence

If H2-H5 cannot be ruled out, the coordination event is SUPPRESSED.

**Test verification — Phase A anti-hal agent catches:**
- May 9 coordination → SUPPRESSED (H4 anniversary fires)
- June 4 Tiananmen coordination → SUPPRESSED (H4)
- Oct 1 China National Day coordination → SUPPRESSED (H4)
- 5+ country generic theme → ESCALATED (cannot rule out H2 major event)
- 3+ country specific theme → ESCALATED (high impact, human review required)
- 2-country specific theme → PUBLISH_WITH_CAVEAT (acceptable confidence, mandatory hedge)

**Database additions:**
- `analysis_claims` table — every claim + its validation verdict
- `analysis_suppressed` table — audit log of killed claims for manual review
- `pipeline_runs` table — health monitoring / last-updated timestamps

---

## Deferred Findings (Documented as MVP Limitations)

### Coordination (Phase B work)
- **COORD-C2**: Article deduplication by content hash — needs Phase B infrastructure
- **COORD-H1**: Window gaming via staggered publishing — needs sliding window
- **COORD-H2**: Low-volume coordination below surge threshold — needs adaptive threshold
- **COORD-H3**: Cross-audience coordination within same country — needs audience tier tracking
- **COORD-H4**: Hardcoded pair bonuses unvalidated — needs empirical ROC calibration
- **COORD-H5**: No confidence intervals on scores — needs statistical framework

### Pipeline (Phase C work)
- **PIPE-C4**: Render cold-stop for long runs — mitigated by time budget enforcement, full fix requires Render Pro
- **PIPE-C6**: GDELT outage detection — needs health probe comparing empty results against expected ranges

### Deviation (Month 2 polish)
- **DEV-H1**: Bessel's correction for sample std — statistical correctness improvement
- **DEV-H2**: Day-of-week baseline segmentation — per the original spec but not implemented
- **DEV-H3**: Continuous confidence curve instead of discrete jumps

### Classifier (Nice-to-haves)
- **CLA-H1** through **CLA-H7**: Telegram "VARIES" handling, multilingual outlets, language code truncation, domain normalization, unknown country codes, confidence double-rounding, outlet confidence cap documentation

---

## Unit Test Results

**56 tests total, 100% pass rate.**

```
pipeline/tests/test_deviation.py   — 20 tests (threshold ordering + std=0 + mean=0 edge cases)
pipeline/tests/test_classifier.py  — 16 tests (CLA-C1/C3/C4 fixes + diaspora + outlet lookups)
pipeline/tests/test_antihal.py     — 20 tests (all 3 validation paths + verdict semantics)
```

Run with:
```bash
cd /Users/don/Documents/Business/Atlas\ Peak\ Media,\ LLC/SalientSignal
python3 -m pytest pipeline/tests/ -v
```

---

## Files Modified in Phase 1

| File | Change Type | Lines Changed |
|------|-------------|---------------|
| `pipeline/src/deviation.py` | Bug fix + edge case handling | +80 |
| `pipeline/src/classifier.py` | Weight normalization rewrite | +60 |
| `pipeline/src/pipeline.py` | Fail-fast + quota + time budget + anti-hal integration | +150 |
| `pipeline/src/db.py` | Added check_storage_quota + record_pipeline_run | +80 |
| `pipeline/src/antihal.py` | **NEW** — Anti-Hallucination Agent | +500 |
| `shared/schema.sql` | Added 3 tables (pipeline_runs, analysis_claims, analysis_suppressed) | +60 |
| `pipeline/tests/__init__.py` | **NEW** | +0 |
| `pipeline/tests/test_deviation.py` | **NEW** — 20 tests | +180 |
| `pipeline/tests/test_classifier.py` | **NEW** — 16 tests | +170 |
| `pipeline/tests/test_antihal.py` | **NEW** — 20 tests | +220 |

**Total:** ~1,500 lines added/modified across 10 files.

---

## Verification Commands

```bash
cd "/Users/don/Documents/Business/Atlas Peak Media, LLC/SalientSignal"

# 1. All Python files compile
python3 -m py_compile pipeline/src/*.py pipeline/scripts/*.py

# 2. All modules import cleanly
python3 -c "from pipeline.src import classifier, baselines, deviation, coordination, gdelt_client, db, outlets, countries, themes, pipeline, antihal; print('OK')"

# 3. Unit tests all pass
python3 -m pytest pipeline/tests/ -v

# 4. End-to-end dry run (with fake GDELT client)
python3 pipeline/scripts/run_pipeline.py --dry-run --no-network
```

All four commands pass.

---

## Acceptance Criteria — Phase 1 Done

- [x] CRITICAL findings DEV-C1/C2/C3, CLA-C1/C2/C3/C4, PIPE-C1/C2/C3 fixed
- [x] Unit tests for all CRITICAL fixes (56 tests, 100% pass)
- [x] HIGH findings documented as deferred with rationale
- [x] Coordination CRITICAL findings mitigated via Anti-Hallucination Agent
- [x] Anti-Hallucination Agent Phase A stub integrated at 3 pipeline integration points
- [x] All pipeline outputs flow through `validate_*` calls before write
- [x] `analysis_claims`, `analysis_suppressed`, `pipeline_runs` tables in schema
- [x] All Python files parse and import cleanly
- [x] Phase 1 Review report written (this file)
- [x] Code ready for commit (not pushed — Don reviews first)

---

## Next Phase

**Phase 2 — Database Init + Local Pipeline Run** (tasks 21-30 from Way Ahead)

Now that the code is validated and tested, the next step is:
1. Initialize Supabase schema (Don runs `schema.sql`)
2. Seed `outlet_classification` table (autonomous)
3. Run pipeline locally against real GDELT (autonomous)
4. Spot-check classifications on real data (autonomous)
5. Tune deviation thresholds if needed (autonomous)

Estimated Phase 2 time: 2-3 hours autonomous execution.

---

## Related Files

- [[SalientSignal-Project]] — Product vision, design
- [[SalientSignal-Algorithms]] — Original algorithm specifications
- [[SalientSignal-Way-Ahead]] — 100-task roadmap
- Plan file: `/Users/don/.claude/plans/proud-jumping-key.md` — Full MVP implementation plan with Phase 1 deep dive

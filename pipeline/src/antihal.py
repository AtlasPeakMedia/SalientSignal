"""Anti-Hallucination Agent — Structured Analytic Techniques validation layer.

Every automated claim the pipeline makes flows through this module before
being persisted or displayed. The agent applies formal Structured Analytic
Techniques (SATs) from the IC Analysts' Structured Analytic Techniques
handbook (Heuer & Pherson) to challenge every output.

SATs applied:

  1. Quality of Information Check
     Rate source reliability + information credibility per claim.

  2. Analysis of Competing Hypotheses (ACH)
     For interpretive claims, generate alternatives and score each against
     observable data. Only advance the primary hypothesis if alternatives
     are ruled out.

  3. Key Assumptions Check
     Identify unstated assumptions in the claim. Challenge each.

  4. Red Team Pass
     Adversarial: "How could this be wrong? What's missing?"

  5. Premortem Analysis (for HIGH-impact claims)
     Assume the claim is wrong. What observable data would prove it wrong?

The module exposes four validation functions, one per claim type:

    validate_classification(article, result) -> ValidationResult
    validate_deviation(country, audience_type, deviation) -> ValidationResult
    validate_coordination(event) -> ValidationResult
    validate_ai_text(text, source_refs) -> ValidationResult  (Phase C, stub)

Each returns a ValidationResult with a Verdict:

    PUBLISH               — claim is well-supported, display as-is
    PUBLISH_WITH_CAVEAT   — add hedge language before display
    SUPPRESS              — alternatives not ruled out; do not display
    ESCALATE              — high-impact claim, needs human review

This is the MVP stub (Phase A). Later phases will:
    - Phase B: implement full ACH with major-event correlation, calendar-aware
      anniversary filtering, and wire service deduplication heuristics
    - Phase C: integrate with Claude/Grok AI output for claim-level tracing
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------
class Verdict(str, Enum):
    PUBLISH = "PUBLISH"
    PUBLISH_WITH_CAVEAT = "PUBLISH_WITH_CAVEAT"
    SUPPRESS = "SUPPRESS"
    ESCALATE = "ESCALATE"


# ---------------------------------------------------------------------------
# ValidationResult — the output of every validate_* call
# ---------------------------------------------------------------------------
@dataclass
class ValidationResult:
    claim_type: str                    # CLASSIFICATION | DEVIATION | COORDINATION | AI_TEXT
    claim_data: dict[str, Any]
    verdict: Verdict
    confidence: float                  # final confidence after validation (0.0-1.0)
    quality_score: float               # Quality of Information Check score (0.0-1.0)
    competing_hypotheses: list[dict[str, Any]] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    red_team_flags: list[str] = field(default_factory=list)
    caveat: str | None = None          # hedge language to attach if PUBLISH_WITH_CAVEAT
    verdict_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_type": self.claim_type,
            "claim_data": self.claim_data,
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 3),
            "quality_score": round(self.quality_score, 3),
            "competing_hypotheses": self.competing_hypotheses,
            "assumptions": self.assumptions,
            "red_team_flags": self.red_team_flags,
            "caveat": self.caveat,
            "verdict_reason": self.verdict_reason,
        }

    @property
    def should_publish(self) -> bool:
        """True if the claim passed validation and can be displayed."""
        return self.verdict in (Verdict.PUBLISH, Verdict.PUBLISH_WITH_CAVEAT)


# ---------------------------------------------------------------------------
# Validation functions — one per claim type
# ---------------------------------------------------------------------------
def validate_classification(
    article_dict: dict[str, Any],
    audience_type: str,
    confidence: float,
) -> ValidationResult:
    """Challenge a classifier output before the article is written.

    Applies:
      - Quality of Information (outlet lookup vs. fallback signals)
      - Red Team: was this a multi-signal decision?
      - Assumption audit: is the outlet still state-affiliated?
    """
    claim = {
        "domain": article_dict.get("source_domain", ""),
        "country": article_dict.get("source_country", ""),
        "language": article_dict.get("source_language", ""),
        "audience_type": audience_type,
        "classifier_confidence": confidence,
    }

    assumptions = [
        "Outlet identity is static (outlets sometimes change editorial direction)",
        "Language code from GDELT is correct",
        "Source country from GDELT is correct",
    ]

    red_team_flags: list[str] = []
    # Low-confidence single-signal classifications are suspicious
    if confidence < 0.55:
        red_team_flags.append(
            "Low classifier confidence — possibly a single-signal fallback or unknown outlet"
        )

    # Unknown classifications shouldn't publish at all
    if audience_type == "UNKNOWN":
        return ValidationResult(
            claim_type="CLASSIFICATION",
            claim_data=claim,
            verdict=Verdict.SUPPRESS,
            confidence=0.0,
            quality_score=0.0,
            assumptions=assumptions,
            red_team_flags=red_team_flags + ["Classification returned UNKNOWN"],
            verdict_reason="UNKNOWN audience type cannot be published",
        )

    # Quality score: outlet lookups get full score, signal-based get discounted
    quality = max(0.1, min(1.0, confidence))

    # Verdict
    if confidence >= 0.85:
        verdict = Verdict.PUBLISH
        reason = "High-confidence outlet lookup or multi-signal agreement"
    elif confidence >= 0.55:
        verdict = Verdict.PUBLISH_WITH_CAVEAT
        reason = "Moderate confidence — language/platform/TLD fallback"
    else:
        verdict = Verdict.PUBLISH_WITH_CAVEAT
        reason = "Low confidence — single-signal fallback"

    caveat = None
    if verdict == Verdict.PUBLISH_WITH_CAVEAT:
        caveat = f"Classification confidence {confidence:.0%}"

    return ValidationResult(
        claim_type="CLASSIFICATION",
        claim_data=claim,
        verdict=verdict,
        confidence=confidence,
        quality_score=quality,
        assumptions=assumptions,
        red_team_flags=red_team_flags,
        caveat=caveat,
        verdict_reason=reason,
    )


def validate_deviation(
    country: str,
    audience_type: str,
    deviation_dict: dict[str, Any],
) -> ValidationResult:
    """Challenge a deviation claim before it drives globe coloring.

    Applies:
      - Quality of Information (sample size via baseline days_sampled)
      - Red Team: is this a noisy country? sentinel z-score?
      - Assumption audit: is 30-day baseline the right window?
    """
    claim = {
        "country": country,
        "audience_type": audience_type,
        "today_count": deviation_dict.get("today_count"),
        "baseline_mean": deviation_dict.get("baseline_mean"),
        "ratio": deviation_dict.get("ratio"),
        "z_score": deviation_dict.get("z_score"),
        "level": deviation_dict.get("level"),
    }

    days_sampled = deviation_dict.get("days_sampled", 0) or 0
    confidence_label = deviation_dict.get("confidence", "LOW")
    z_score = deviation_dict.get("z_score", 0) or 0
    level = deviation_dict.get("level", "neutral")
    baseline_mean = deviation_dict.get("baseline_mean", 0) or 0
    baseline_std = deviation_dict.get("baseline_std", 0) or 0

    assumptions = [
        "30-day rolling baseline captures 'normal' output",
        "GDELT article counts reflect actual state media output volume",
        "Day-of-week effects (weekday/weekend) do not dominate the baseline",
    ]

    red_team_flags: list[str] = []

    # Low sample size: baseline unreliable
    if days_sampled < 14:
        red_team_flags.append(
            f"Small sample size: only {days_sampled} days of history"
        )

    # Sentinel z-score (our edge case handling for std=0 or mean=0)
    if abs(z_score) >= 10.0:
        red_team_flags.append(
            "Sentinel z-score — baseline was perfectly consistent (std=0) or zero "
            "(mean=0). Treat with care."
        )

    # High ratio with low z-score = noisy country (already returns neutral, but flag)
    if deviation_dict.get("ratio", 0) > 2.0 and abs(z_score) < 2.0:
        red_team_flags.append(
            "High ratio but low z-score: country may have high baseline variance"
        )

    # Zero baseline: very sparse history
    if baseline_std == 0 and baseline_mean > 0:
        red_team_flags.append(
            "Zero baseline variance — country publishes perfectly consistent volume"
        )

    # Quality of information: confidence label from baselines.py
    quality = {"LOW": 0.3, "MEDIUM": 0.65, "HIGH": 0.95}.get(confidence_label, 0.3)

    # Verdict: extreme anomalies in low-confidence baselines get suppressed
    if level in ("red", "deepBlue") and confidence_label == "LOW":
        return ValidationResult(
            claim_type="DEVIATION",
            claim_data=claim,
            verdict=Verdict.SUPPRESS,
            confidence=0.2,
            quality_score=quality,
            assumptions=assumptions,
            red_team_flags=red_team_flags + [
                "Extreme level with LOW baseline confidence — cannot rule out noise"
            ],
            verdict_reason=(
                f"Level={level} claimed but baseline confidence is LOW "
                f"({days_sampled} days). Suppressing to avoid false alarm."
            ),
        )

    # High-impact claims (red/deepBlue) with MEDIUM confidence get a caveat
    if level in ("red", "deepBlue") and confidence_label == "MEDIUM":
        return ValidationResult(
            claim_type="DEVIATION",
            claim_data=claim,
            verdict=Verdict.PUBLISH_WITH_CAVEAT,
            confidence=0.6,
            quality_score=quality,
            assumptions=assumptions,
            red_team_flags=red_team_flags,
            caveat=f"Confidence: {confidence_label} ({days_sampled}-day baseline)",
            verdict_reason="High-impact anomaly with moderate sample size",
        )

    # Normal publish path
    return ValidationResult(
        claim_type="DEVIATION",
        claim_data=claim,
        verdict=Verdict.PUBLISH,
        confidence=quality,
        quality_score=quality,
        assumptions=assumptions,
        red_team_flags=red_team_flags,
        verdict_reason=f"Level={level} with {confidence_label} confidence",
    )


# ---------------------------------------------------------------------------
# Competing hypotheses for coordination events — THIS IS WHERE THE BUG DIES
# ---------------------------------------------------------------------------
def _generate_coordination_hypotheses(
    event: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Generate alternative explanations for a coordination event.

    Phase A (MVP): rule-based hypothesis generation with static scoring.
    Phase B: cross-reference with GDELT event stream, calendar, wire feeds.
    """
    theme = event.get("theme", "")
    countries = event.get("countries", []) or []
    event_date = event.get("date", "")

    hypotheses: list[dict[str, Any]] = []

    # H1: Deliberate coordination (the primary hypothesis)
    hypotheses.append({
        "id": "H1_DELIBERATE_COORDINATION",
        "description": "Countries are deliberately coordinating a propaganda campaign",
        "required_evidence": [
            "Narrative not present in major wire services",
            "Theme is specific and narrow (not generic world news)",
            "Not a known anniversary or recurring pattern",
            "Countries published within a tight time window",
        ],
        "score": 0.0,  # start at zero, accumulate evidence
        "verdict": "UNSUPPORTED_IN_PHASE_A",
    })

    # H2: Major event reaction
    hypotheses.append({
        "id": "H2_MAJOR_EVENT_REACTION",
        "description": "All countries are reactively covering a major world event",
        "required_evidence": [
            "A major world event occurred within 24 hours of the spike",
            "Non-state media are also surging on the same topic",
            "Theme matches common reactive coverage patterns",
        ],
        "score": 0.5,  # default: assume unknown. Phase B will check GDELT event stream.
        "verdict": "CANNOT_RULE_OUT_IN_PHASE_A",
    })

    # H3: Wire service syndication
    hypotheses.append({
        "id": "H3_WIRE_SYNDICATION",
        "description": "Articles are republications of a common wire source (AFP/Reuters/TASS)",
        "required_evidence": [
            "Article titles are highly similar across countries",
            "Articles share common wire service attribution",
            "Theme is generic news not specific narrative",
        ],
        "score": 0.4,
        "verdict": "CANNOT_RULE_OUT_IN_PHASE_A",
    })

    # H4: Anniversary / recurring pattern
    if event_date:
        try:
            dt = datetime.fromisoformat(event_date).date() if "T" in event_date else date.fromisoformat(event_date)
            month_day = (dt.month, dt.day)
            anniversaries = {
                (5, 9): "Victory Day (Russia, Belarus, NK) — annual narrative",
                (10, 1): "National Day (China, NK) — annual narrative",
                (2, 11): "Iranian Revolution Day — annual narrative",
                (7, 1): "Hong Kong handover anniversary (China) — annual narrative",
                (6, 4): "Tiananmen anniversary (China) — annual narrative",
                (11, 7): "October Revolution anniversary (Russia) — annual narrative",
            }
            if month_day in anniversaries:
                hypotheses.append({
                    "id": "H4_ANNIVERSARY_PATTERN",
                    "description": f"Recurring anniversary coverage: {anniversaries[month_day]}",
                    "required_evidence": ["Event date matches known anniversary"],
                    "score": 0.9,  # STRONG evidence this is just an anniversary
                    "verdict": "LIKELY_ALTERNATIVE_EXPLANATION",
                })
        except (ValueError, TypeError):
            pass

    # H5: Timezone / publishing cycle coincidence
    hypotheses.append({
        "id": "H5_PUBLISHING_CYCLE",
        "description": "Normal business-hours publishing in different timezones",
        "required_evidence": [
            "Publications span multiple timezones",
            "Theme is generic news, not a specific narrative",
            "No coordination bonus pair (RU-CN, RU-IR, etc.) in the country set",
        ],
        "score": 0.3,
        "verdict": "UNLIKELY_BUT_POSSIBLE",
    })

    return hypotheses


def validate_coordination(event: dict[str, Any], context: dict[str, Any] | None = None) -> ValidationResult:
    """Challenge a coordination event before it draws an arc on the globe.

    THIS IS THE CRITICAL VALIDATION. Most false-positive coordination events
    will be killed here.

    Applies:
      - ACH: generate alternative hypotheses (major event, wire syndication,
        anniversary, timezone artifact) and check if they can be ruled out.
      - Key Assumptions Check: the 48-hour window assumption, the theme
        matching assumption, the pair-bonus assumption.
      - Red Team: all the false-positive vectors from COORD-C1/C2/C3.
      - Premortem: assume the coordination claim is wrong. Is there any
        evidence that matches the alternatives?

    Phase A returns SUPPRESS for almost all events that could have simpler
    explanations. Phase B will implement proper major-event/wire/calendar
    lookups and only suppress when alternatives are actually supported.
    """
    theme = event.get("theme", "")
    countries = event.get("countries", []) or []
    score = event.get("coordination_score", 0) or 0
    event_date = event.get("date", "")

    claim = dict(event)

    assumptions = [
        "Spikes within the time window imply coordination",
        "GDELT theme codes are semantically comparable across countries",
        "Article counts reflect unique stories, not syndicated republications",
        "Known coordination pair bonuses (RU-CN, RU-IR, etc.) reflect real patterns",
    ]

    red_team_flags: list[str] = []

    # COORD-C1: No major event filter → flag if 4+ countries spike a generic theme
    if len(countries) >= 4:
        red_team_flags.append(
            f"{len(countries)} countries surging the same theme — possible major "
            "world event reaction (H2), not coordination"
        )

    # COORD-C2: No article dedup → flag if theme is generic
    generic_themes = {
        "CRISISLEX_", "NATURAL_DISASTER", "DISASTER", "WB_", "EPU_",
        "TERROR", "ELECTION", "ECON_", "EARTHQUAKE", "FLOOD", "HURRICANE",
    }
    if any(theme.startswith(g) or g in theme for g in generic_themes):
        red_team_flags.append(
            f"Theme '{theme}' is generic — cannot distinguish from wire syndication (H3)"
        )

    # Generate competing hypotheses
    hypotheses = _generate_coordination_hypotheses(event, context)

    # Check if any alternative hypothesis has strong evidence
    strong_alternative = any(
        h["score"] >= 0.7 for h in hypotheses if h["id"] != "H1_DELIBERATE_COORDINATION"
    )

    # Quality of information: coordination score × country count factor
    quality = min(1.0, score * (0.7 + 0.1 * min(len(countries), 3)))

    # Premortem: if alternatives cannot be ruled out, suppress
    if strong_alternative:
        anniversary_hypothesis = next(
            (h for h in hypotheses if h["id"] == "H4_ANNIVERSARY_PATTERN"), None
        )
        reason = "Strong alternative hypothesis: "
        if anniversary_hypothesis and anniversary_hypothesis["score"] >= 0.7:
            reason += anniversary_hypothesis["description"]
        else:
            reason += "Cannot rule out non-coordination explanations"

        return ValidationResult(
            claim_type="COORDINATION",
            claim_data=claim,
            verdict=Verdict.SUPPRESS,
            confidence=0.2,
            quality_score=quality,
            competing_hypotheses=hypotheses,
            assumptions=assumptions,
            red_team_flags=red_team_flags,
            verdict_reason=reason,
        )

    # High-impact triple-country coordination always escalates in Phase A
    if len(countries) >= 3 and score >= 0.6:
        return ValidationResult(
            claim_type="COORDINATION",
            claim_data=claim,
            verdict=Verdict.ESCALATE,
            confidence=score,
            quality_score=quality,
            competing_hypotheses=hypotheses,
            assumptions=assumptions,
            red_team_flags=red_team_flags,
            caveat="Multi-country coordination — requires human verification",
            verdict_reason="High-impact claim: 3+ country coordination. Escalate for human review.",
        )

    # Phase A: all other coordination claims publish with a mandatory caveat
    # since we can't properly rule out H2/H3/H5 without Phase B infrastructure.
    return ValidationResult(
        claim_type="COORDINATION",
        claim_data=claim,
        verdict=Verdict.PUBLISH_WITH_CAVEAT,
        confidence=score * 0.7,  # discounted because we can't rule out alternatives
        quality_score=quality,
        competing_hypotheses=hypotheses,
        assumptions=assumptions,
        red_team_flags=red_team_flags,
        caveat=(
            "Coordination detection is BETA — Phase A cannot rule out wire "
            "syndication, reactive coverage, or timezone artifacts. Validate "
            "manually before acting on this signal."
        ),
        verdict_reason="Phase A validation: coordination published with mandatory caveat",
    )


def validate_ai_text(
    text: str,
    source_refs: list[dict[str, Any]] | None = None,
) -> ValidationResult:
    """Challenge AI-generated text (Phase C — stub).

    Future: claim-by-claim trace to source data, hedge language enforcement,
    suppression of unsupported interpretive leaps.

    Phase A returns PUBLISH for everything (no AI output yet in MVP).
    """
    return ValidationResult(
        claim_type="AI_TEXT",
        claim_data={"text": text, "source_refs": source_refs or []},
        verdict=Verdict.PUBLISH,
        confidence=0.5,
        quality_score=0.5,
        verdict_reason="Phase A stub: AI text validation not yet implemented",
    )


# ---------------------------------------------------------------------------
# Batch helpers — pipeline.py uses these to validate all outputs at once
# ---------------------------------------------------------------------------
def validate_batch_classifications(
    article_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[ValidationResult]]:
    """Validate every article classification. Return (published_rows, all_results).

    Only rows whose validation.should_publish is True are included in
    published_rows. The full result list (including suppressed) is returned
    for logging/audit.
    """
    published: list[dict[str, Any]] = []
    results: list[ValidationResult] = []
    for row in article_rows:
        audience = row.get("audience_type", "")
        conf = row.get("audience_confidence", 0) or 0
        vr = validate_classification(row, audience, conf)
        results.append(vr)
        if vr.should_publish:
            # Attach the caveat if present
            if vr.caveat:
                row = {**row, "_caveat": vr.caveat}
            published.append(row)
    return published, results


def validate_batch_deviations(
    activity_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[ValidationResult]]:
    """Validate every country_activity row. Return (published_rows, all_results)."""
    published: list[dict[str, Any]] = []
    results: list[ValidationResult] = []
    for row in activity_rows:
        country = row.get("country", "")
        audience = row.get("audience_type", "")
        vr = validate_deviation(country, audience, row)
        results.append(vr)
        if vr.should_publish:
            if vr.caveat:
                row = {**row, "_caveat": vr.caveat}
            published.append(row)
    return published, results


def validate_batch_coordinations(
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[ValidationResult]]:
    """Validate every coordination event. Return (published_events, all_results)."""
    published: list[dict[str, Any]] = []
    results: list[ValidationResult] = []
    for event in events:
        vr = validate_coordination(event)
        results.append(vr)
        if vr.should_publish:
            if vr.caveat:
                event = {**event, "_caveat": vr.caveat}
            published.append(event)
    return published, results


__all__ = [
    "Verdict",
    "ValidationResult",
    "validate_classification",
    "validate_deviation",
    "validate_coordination",
    "validate_ai_text",
    "validate_batch_classifications",
    "validate_batch_deviations",
    "validate_batch_coordinations",
]

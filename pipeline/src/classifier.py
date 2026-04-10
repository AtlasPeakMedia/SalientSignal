"""Audience classifier — Algorithm 1 from SalientSignal-Algorithms.md.

For each ingested article, decide whether the content targets a DOMESTIC,
INTERNATIONAL, or DIASPORA audience. The classifier combines multiple signals
in priority order:

    Signal 1 — Outlet identity (highest confidence). If the domain is in the
               outlets database, the audience is whatever that record says.
    Signal 2 — Publication language vs. country official languages.
    Signal 3 — Platform (vk.com domestic, tiktok international, etc.).
    Signal 4 — Domain TLD (weakest, used as a tiebreaker).

The function returns a tuple `(audience_type, confidence)` where audience_type
is one of "DOMESTIC", "INTERNATIONAL", "DIASPORA", or "UNKNOWN".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .countries import get_country
from .outlets import _normalize_domain, get_outlet

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Article record (lightweight DTO so the classifier doesn't need to depend on
# pandas / GDELT internals)
# ---------------------------------------------------------------------------
@dataclass
class Article:
    url: str
    domain: str
    source_country: str  # ISO 3166-1 alpha-2 (NOT FIPS)
    language: str  # ISO 639-1
    title: str = ""
    pub_date: str = ""
    tone: float = 0.0
    themes: list[str] | None = None

    @classmethod
    def from_gdelt_row(cls, row: dict[str, Any]) -> "Article":
        """Construct from a GDELT DOC 2.0 ArtList row.

        GDELT field names (as returned by gdeltdoc):
            url, url_mobile, title, seendate, socialimage, domain, language,
            sourcecountry
        Country is returned by GDELT as a 2-letter FIPS code (sometimes ISO).
        We normalize via the countries lookup downstream.
        """
        return cls(
            url=row.get("url", ""),
            domain=_normalize_domain(row.get("domain", "")),
            source_country=str(row.get("sourcecountry") or "").upper(),
            language=str(row.get("language") or "").lower()[:2],
            title=row.get("title", ""),
            pub_date=row.get("seendate", ""),
        )


# ---------------------------------------------------------------------------
# Platform → audience hints
# ---------------------------------------------------------------------------
PLATFORM_AUDIENCE: dict[str, dict[str, Any]] = {
    "vk.com":       {"audience": "DOMESTIC",      "country": "RU", "confidence": 0.90},
    "weibo.com":    {"audience": "DOMESTIC",      "country": "CN", "confidence": 0.90},
    "douyin.com":   {"audience": "DOMESTIC",      "country": "CN", "confidence": 0.95},
    "tiktok.com":   {"audience": "INTERNATIONAL", "country": "CN", "confidence": 0.80},
    "twitter.com":  {"audience": "INTERNATIONAL", "country": "*",  "confidence": 0.70},
    "x.com":        {"audience": "INTERNATIONAL", "country": "*",  "confidence": 0.70},
    "facebook.com": {"audience": "INTERNATIONAL", "country": "*",  "confidence": 0.50},
    "telegram.org": {"audience": "VARIES",        "country": "*",  "confidence": 0.50},
    "t.me":         {"audience": "VARIES",        "country": "*",  "confidence": 0.50},
}


# ---------------------------------------------------------------------------
# Domain TLD → audience hints
# ---------------------------------------------------------------------------
DOMESTIC_TLDS: frozenset[str] = frozenset(
    {"ru", "cn", "ir", "tr", "sa", "qa", "ae", "eg", "sy", "by", "ve", "cu", "kp"}
)
INTERNATIONAL_TLDS: frozenset[str] = frozenset({"com", "org", "net", "info", "tv", "news"})


# ---------------------------------------------------------------------------
# DIASPORA targeting patterns: certain (origin_country, content_language)
# pairs targeting specific destination countries.
# Expanded per red team CLA-C2 finding: now covers TR, IR, VN, UZ in addition
# to RU, CN. Add more as documented state media diaspora programs are found.
# ---------------------------------------------------------------------------
DIASPORA_LANGUAGE_HINTS: dict[str, set[str]] = {
    # Russia targets Russian-speakers in Germany, France, Spain, Israel
    "RU": {"de", "fr", "es", "he"},
    # China targets Chinese diaspora in SEA (Indonesia, Malaysia, Thailand)
    "CN": {"id", "ms", "th"},
    # Turkey targets Turkish diaspora in Germany, Netherlands, Austria, Belgium
    "TR": {"de", "nl", "fr"},
    # Iran targets Persian diaspora in US (blocked), Europe, and Farsi speakers
    "IR": {"en", "de", "fr"},
    # Vietnam targets Vietnamese diaspora in US/Australia/France
    "VN": {"en", "fr"},
    # Uzbekistan targets Uzbek diaspora in Russia
    "UZ": {"ru"},
    # Kazakhstan targets Kazakh diaspora in Russia
    "KZ": {"ru"},
}

# Signal weights used in the final classify_audience() score combination.
# Normalized so the maximum achievable score from any single signal
# is <= SIGNAL_MAX_WEIGHT[signal]. Used for confidence denominator.
SIGNAL_WEIGHT_LANGUAGE = 0.8
SIGNAL_WEIGHT_PLATFORM = 0.7
SIGNAL_WEIGHT_TLD = 0.3
SIGNAL_WEIGHT_TOTAL = (
    SIGNAL_WEIGHT_LANGUAGE + SIGNAL_WEIGHT_PLATFORM + SIGNAL_WEIGHT_TLD
)

# Minimum number of independent signals required for high confidence in a
# non-outlet-lookup classification. Single-signal classifications are capped
# at MAX_SINGLE_SIGNAL_CONFIDENCE to prevent false certainty.
MIN_SIGNALS_FOR_HIGH_CONFIDENCE = 2
MAX_SINGLE_SIGNAL_CONFIDENCE = 0.55


def classify_by_outlet(domain: str) -> tuple[str | None, float, dict[str, Any] | None]:
    """Highest-confidence signal: direct outlet lookup."""
    record = get_outlet(domain)
    if not record:
        return None, 0.0, None
    return record.audience_type, max(0.0, min(1.0, record.confidence)), {
        "outlet_name": record.outlet_name,
        "country": record.country,
        "languages": list(record.languages),
    }


def classify_by_language(article_language: str, source_country: str) -> tuple[str, float]:
    """If a country publishes in its own language, that's domestic. Otherwise international."""
    if not article_language or not source_country:
        return "UNKNOWN", 0.0
    official = {lang.lower() for lang in get_country(source_country.upper()).official_languages} \
        if get_country(source_country.upper()) else set()
    lang = article_language.lower()
    if not official:
        return "UNKNOWN", 0.0
    if lang in official:
        return "DOMESTIC", 0.75
    # Check diaspora patterns: e.g. RT-DE in German targets diaspora, not pure international.
    diaspora_langs = DIASPORA_LANGUAGE_HINTS.get(source_country.upper(), set())
    if lang in diaspora_langs:
        return "DIASPORA", 0.70
    return "INTERNATIONAL", 0.85


def classify_by_platform(domain: str) -> tuple[str | None, float]:
    """Platform-level audience hints (only if the domain matches a known platform)."""
    if not domain:
        return None, 0.0
    host = _normalize_domain(domain).split("/", 1)[0]
    # Walk parent domains to catch e.g. "subdomain.vk.com"
    parts = host.split(".")
    for i in range(len(parts) - 1):
        candidate = ".".join(parts[i:])
        hit = PLATFORM_AUDIENCE.get(candidate)
        if hit and hit["audience"] != "VARIES":
            return hit["audience"], float(hit["confidence"])
    return None, 0.0


def classify_by_domain(domain: str) -> tuple[str, float]:
    """TLD-based weak signal — used as a tiebreaker."""
    if not domain:
        return "UNKNOWN", 0.0
    host = _normalize_domain(domain).split("/", 1)[0]
    if "." not in host:
        return "UNKNOWN", 0.0
    tld = host.rsplit(".", 1)[-1]
    if tld in DOMESTIC_TLDS:
        return "DOMESTIC", 0.60
    if tld in INTERNATIONAL_TLDS:
        return "INTERNATIONAL", 0.40
    return "UNKNOWN", 0.0


# ---------------------------------------------------------------------------
# Final classifier — combines all signals
# ---------------------------------------------------------------------------
def classify_audience(article: Article) -> tuple[str, float]:
    """Algorithm 1 — return (audience_type, confidence) for an article.

    Red team fixes (CLA-C1, CLA-C3, CLA-C4):

    - CLA-C1: Unknown data no longer defaults to INTERNATIONAL 100%.
              Fallback now requires at least 2 independent signals
              agreeing for HIGH confidence, and single-signal results
              are capped at MAX_SINGLE_SIGNAL_CONFIDENCE (0.55).

    - CLA-C3: Confidence is now normalized against the theoretical
              maximum possible signal strength (SIGNAL_WEIGHT_TOTAL = 1.8),
              not the sum of activated signals. This prevents single-signal
              activations from appearing as 100% confidence.

    - CLA-C4: When no signals fire, return UNKNOWN (not default to a
              class). Unknown outlets in unusual languages now flow to
              UNKNOWN instead of being misclassified as INTERNATIONAL.
    """
    # Signal 1: Direct outlet lookup. Trust completely if available.
    outlet_audience, outlet_conf, _meta = classify_by_outlet(article.domain)
    if outlet_audience:
        # Cap top confidence at 0.95 — leave room for cases where outlet metadata is stale.
        return outlet_audience, min(outlet_conf, 0.95)

    scores: dict[str, float] = {"DOMESTIC": 0.0, "INTERNATIONAL": 0.0, "DIASPORA": 0.0}
    signals_fired: dict[str, list[str]] = {
        "DOMESTIC": [], "INTERNATIONAL": [], "DIASPORA": [],
    }

    # Signal 2: language vs country official languages (weight 0.8)
    lang_class, lang_conf = classify_by_language(article.language, article.source_country)
    if lang_class in scores:
        scores[lang_class] += SIGNAL_WEIGHT_LANGUAGE * lang_conf
        signals_fired[lang_class].append("language")

    # Signal 3: platform (weight 0.7)
    plat_class, plat_conf = classify_by_platform(article.domain)
    if plat_class in scores:
        scores[plat_class] += SIGNAL_WEIGHT_PLATFORM * plat_conf
        signals_fired[plat_class].append("platform")

    # Signal 4: TLD (weight 0.3)
    tld_class, tld_conf = classify_by_domain(article.domain)
    if tld_class in scores:
        scores[tld_class] += SIGNAL_WEIGHT_TLD * tld_conf
        signals_fired[tld_class].append("tld")

    # Check if any signals fired at all
    total_activated = sum(scores.values())
    if total_activated <= 0:
        return "UNKNOWN", 0.0

    best = max(scores, key=scores.get)
    best_score = scores[best]

    # CLA-C3 FIX: Normalize confidence against theoretical maximum,
    # not sum of activated signals. This prevents single-signal false
    # certainty.
    confidence = best_score / SIGNAL_WEIGHT_TOTAL

    # CLA-C1 FIX: Single-signal classifications are capped. A single
    # signal is insufficient evidence for high confidence.
    num_signals_for_best = len(signals_fired[best])
    if num_signals_for_best < MIN_SIGNALS_FOR_HIGH_CONFIDENCE:
        confidence = min(confidence, MAX_SINGLE_SIGNAL_CONFIDENCE)

    # Tiebreaker: if DIASPORA and INTERNATIONAL scored identically,
    # prefer DIASPORA (it's a more specific claim and the red team
    # flagged that DIASPORA was under-weighted).
    if best == "INTERNATIONAL" and scores["DIASPORA"] > 0 and scores["DIASPORA"] >= scores["INTERNATIONAL"] * 0.95:
        best = "DIASPORA"

    return best, round(min(confidence, 1.0), 3)


__all__ = [
    "Article",
    "classify_audience",
    "classify_by_outlet",
    "classify_by_language",
    "classify_by_platform",
    "classify_by_domain",
    "PLATFORM_AUDIENCE",
    "DOMESTIC_TLDS",
    "INTERNATIONAL_TLDS",
]

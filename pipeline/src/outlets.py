"""Outlet classification database loader and lookup functions.

The outlet database is a JSON file (`pipeline/data/outlets.json`) that maps
state-media domains to their country, audience type, languages, and ownership.
This module provides simple lookup helpers used by the classifier and the
pipeline orchestrator.

Key functions:
    load_outlets()           — read outlets.json once and cache the result
    get_outlet(domain)       — return the OutletRecord for a domain (or None)
    is_state_media(domain)   — True if the domain is in the database
    get_audience_type(domain)— DOMESTIC | INTERNATIONAL | DIASPORA | None
    get_outlets_for_country(iso2)
    get_all_outlets()
    get_monitored_countries()— set of all ISO codes appearing in outlets.json
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Hard FVEY exclusion — enforced at load time
FVEY_COUNTRIES: frozenset[str] = frozenset({"US", "GB", "CA", "AU", "NZ"})

# Path to the outlets database (relative to this file: src/outlets.py -> ../data/outlets.json)
DEFAULT_OUTLETS_PATH = Path(__file__).resolve().parent.parent / "data" / "outlets.json"


@dataclass(frozen=True)
class OutletRecord:
    """A single state-media outlet classification entry."""

    domain: str
    country: str  # ISO 3166-1 alpha-2
    audience_type: str  # DOMESTIC | INTERNATIONAL | DIASPORA
    outlet_name: str
    outlet_type: str = ""
    languages: tuple[str, ...] = field(default_factory=tuple)
    is_state_owned: bool = False
    is_state_aligned: bool = False
    confidence: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutletRecord":
        return cls(
            domain=data["domain"].lower().strip(),
            country=data["country"].upper(),
            audience_type=data["audience_type"].upper(),
            outlet_name=data["outlet_name"],
            outlet_type=data.get("outlet_type", ""),
            languages=tuple(data.get("languages", [])),
            is_state_owned=bool(data.get("is_state_owned", False)),
            is_state_aligned=bool(data.get("is_state_aligned", False)),
            confidence=float(data.get("confidence", 1.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "country": self.country,
            "audience_type": self.audience_type,
            "outlet_name": self.outlet_name,
            "outlet_type": self.outlet_type,
            "languages": list(self.languages),
            "is_state_owned": self.is_state_owned,
            "is_state_aligned": self.is_state_aligned,
            "confidence": self.confidence,
        }


def _normalize_domain(domain: str) -> str:
    """Extract and normalize the canonical hostname from any URL-like input.

    P2-C3 red team fix — handles all the real-world formats GDELT returns:
      - https://rt.com/article/123 → rt.com
      - http://www.rt.com/ → rt.com
      - m.rt.com → m.rt.com (mobile subdomain; parent walk-up catches it)
      - rt.com:443 → rt.com (strips port)
      - rt.com. → rt.com (strips trailing DNS dot)
      - rt.com?utm_source=foo → rt.com (strips query string)
      - news.google.com/rss/articles/... → news.google.com (stops at host)
      - "  RT.COM  " → rt.com (trims + lowercases)
      - bare host like "tass.ru" → tass.ru (passthrough)

    Known limitations:
      - Google News redirect URLs (news.google.com/rss/...) will normalize to
        news.google.com, not the underlying source. There's no way to unwrap
        these without fetching the URL. Handle at outlet classification stage.
      - Shortened URLs (bit.ly, t.co) can't be unwrapped here either.
    """
    if not domain:
        return ""

    d = domain.strip().lower()
    if not d:
        return ""

    # Strip scheme if present
    if "://" in d:
        d = d.split("://", 1)[1]

    # Strip userinfo (user:pass@host)
    if "@" in d:
        # Only split on @ if it comes before the first / (otherwise it's in a path)
        slash_pos = d.find("/")
        at_pos = d.find("@")
        if slash_pos == -1 or at_pos < slash_pos:
            d = d.split("@", 1)[1]

    # Strip everything after the first path separator
    for sep in ("/", "?", "#"):
        if sep in d:
            d = d.split(sep, 1)[0]

    # Strip port number
    if ":" in d:
        d = d.split(":", 1)[0]

    # Strip leading/trailing dots (DNS allows trailing dot, but our DB doesn't)
    d = d.strip(".")

    # Strip www. prefix (canonicalize)
    if d.startswith("www."):
        d = d[4:]

    # Collapse consecutive dots (malformed input protection)
    while ".." in d:
        d = d.replace("..", ".")

    return d


@lru_cache(maxsize=1)
def load_outlets(path: Path | None = None) -> dict[str, OutletRecord]:
    """Load the outlets.json database into a dict keyed by canonical domain.

    Cached so that repeated calls within a single pipeline run do not re-read
    the file. FVEY-country outlets are filtered out at load time as a defensive
    layer (the source file should already exclude them).
    """
    target = path or DEFAULT_OUTLETS_PATH
    if not target.exists():
        raise FileNotFoundError(
            f"outlets.json not found at {target}. "
            "Run from the pipeline/ directory or pass an explicit path."
        )

    with target.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    outlets_list = raw.get("outlets", [])
    by_domain: dict[str, OutletRecord] = {}
    skipped_fvey = 0
    for entry in outlets_list:
        try:
            record = OutletRecord.from_dict(entry)
        except (KeyError, ValueError) as exc:  # pragma: no cover — guard against bad data
            logger.warning("Skipping malformed outlet entry %r: %s", entry, exc)
            continue
        if record.country in FVEY_COUNTRIES:
            skipped_fvey += 1
            logger.warning(
                "FVEY-country outlet found in outlets.json (excluded): %s (%s)",
                record.domain,
                record.country,
            )
            continue
        by_domain[record.domain] = record

    logger.info("Loaded %d outlets from %s", len(by_domain), target)
    if skipped_fvey:
        logger.warning("Excluded %d FVEY-country outlets", skipped_fvey)
    return by_domain


def get_outlet(domain: str) -> OutletRecord | None:
    """Look up an outlet by domain. Returns None if not in the database.

    Tries the normalized hostname first, then walks UP the subdomain chain
    so that "m.rt.com", "english.cgtn.com", "arabic.rt.com" all resolve to
    their parent outlet when the parent is registered.

    P2-C3 fix: _normalize_domain now extracts the bare hostname before this
    function sees it, so the lookup no longer has to deal with paths,
    query strings, ports, etc.
    """
    if not domain:
        return None
    db = load_outlets()
    normalized = _normalize_domain(domain)
    if not normalized:
        return None

    # Try the full normalized hostname first (most specific match wins).
    if normalized in db:
        return db[normalized]

    # Walk up the subdomain chain: "m.rt.com" → "rt.com"
    parts = normalized.split(".")
    while len(parts) > 2:
        parts.pop(0)
        candidate = ".".join(parts)
        if candidate in db:
            return db[candidate]

    return None


def is_state_media(domain: str) -> bool:
    """True if the domain matches a known state-media outlet."""
    return get_outlet(domain) is not None


def get_audience_type(domain: str) -> str | None:
    """Return DOMESTIC | INTERNATIONAL | DIASPORA, or None if unknown."""
    record = get_outlet(domain)
    return record.audience_type if record else None


def get_outlets_for_country(country: str) -> list[OutletRecord]:
    """All outlets registered to a given ISO 3166-1 alpha-2 country code."""
    cc = country.upper()
    return [r for r in load_outlets().values() if r.country == cc]


def get_all_outlets() -> list[OutletRecord]:
    """Every outlet in the database."""
    return list(load_outlets().values())


def get_monitored_countries() -> set[str]:
    """Set of ISO codes for every country that has at least one outlet."""
    return {r.country for r in load_outlets().values()}

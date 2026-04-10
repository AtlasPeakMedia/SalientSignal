"""Country reference data — FIPS/ISO mapping, official languages, regions.

The data lives in `shared/countries.json` (one canonical source for both the
pipeline and the frontend). This module provides typed lookup helpers.

Key functions:
    load_countries()                  — read shared/countries.json once
    get_country(iso2)                 — by ISO 3166-1 alpha-2
    get_country_by_fips(fips)         — by FIPS 10-4 (legacy GDELT format)
    get_official_languages(iso2)      — list of ISO 639-1 codes
    fips_to_iso(fips)                 — bare FIPS->ISO2 lookup
    iso_to_fips(iso2)                 — bare ISO2->FIPS lookup
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Repo layout: pipeline/src/countries.py -> ../../shared/countries.json
DEFAULT_COUNTRIES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "shared" / "countries.json"
)


@dataclass(frozen=True)
class CountryRecord:
    fips: str
    iso2: str
    iso3: str
    name: str
    region: str
    official_languages: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CountryRecord":
        return cls(
            fips=data["fips"].upper(),
            iso2=data["iso2"].upper(),
            iso3=data["iso3"].upper(),
            name=data["name"],
            region=data.get("region", ""),
            official_languages=tuple(data.get("official_languages", [])),
        )


@lru_cache(maxsize=1)
def load_countries(path: Path | None = None) -> dict[str, CountryRecord]:
    """Load shared/countries.json into a dict keyed by ISO2."""
    target = path or DEFAULT_COUNTRIES_PATH
    if not target.exists():
        raise FileNotFoundError(
            f"countries.json not found at {target}. "
            "Expected at shared/countries.json relative to repo root."
        )

    with target.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    by_iso2: dict[str, CountryRecord] = {}
    for iso2, entry in raw.get("countries", {}).items():
        try:
            record = CountryRecord.from_dict(entry)
        except (KeyError, ValueError) as exc:  # pragma: no cover
            logger.warning("Skipping malformed country entry %s: %s", iso2, exc)
            continue
        by_iso2[record.iso2] = record

    logger.info("Loaded %d countries from %s", len(by_iso2), target)
    return by_iso2


@lru_cache(maxsize=1)
def _fips_index() -> dict[str, str]:
    """Reverse index FIPS -> ISO2."""
    return {r.fips: r.iso2 for r in load_countries().values() if r.fips}


def get_country(iso2: str) -> CountryRecord | None:
    """Look up a country by ISO 3166-1 alpha-2 code."""
    return load_countries().get(iso2.upper())


def get_country_by_fips(fips: str) -> CountryRecord | None:
    """Look up a country by FIPS 10-4 code (the format GDELT returns)."""
    iso2 = _fips_index().get(fips.upper())
    return get_country(iso2) if iso2 else None


def get_official_languages(iso2: str) -> list[str]:
    """List of ISO 639-1 official language codes for a country, or [] if unknown."""
    record = get_country(iso2)
    return list(record.official_languages) if record else []


def fips_to_iso(fips: str) -> str | None:
    """Translate a FIPS 10-4 code to ISO 3166-1 alpha-2."""
    if not fips:
        return None
    return _fips_index().get(fips.upper())


def iso_to_fips(iso2: str) -> str | None:
    """Translate an ISO 3166-1 alpha-2 code to FIPS 10-4."""
    record = get_country(iso2)
    return record.fips if record else None

"""GDELT theme tag extraction.

Phase 1/2 deliberately stays simple: we use GDELT's existing GKG theme codes
verbatim. Algorithm 5 in the spec describes a richer custom theme taxonomy
(NATO_AGGRESSION, WESTERN_HYPOCRISY, etc.) but that's deferred to Phase 8 once
the pipeline is collecting data.

Public surface:

    extract_themes(article_row)         — pull theme codes off a GDELT row
    aggregate_themes(rows)              — count themes across many rows
    load_theme_labels()                 — read pipeline/data/theme_labels.json
    label_for(code)                     — human-readable label for a code
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

DEFAULT_LABELS_PATH = Path(__file__).resolve().parent.parent / "data" / "theme_labels.json"


def _split_themes(value: Any) -> list[str]:
    """GDELT returns themes either as a semicolon-separated string or a list.

    Some clients return CSV; some return raw GKG GraphML; some return None.
    Normalize all of those into a clean list of theme codes.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if v]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        # GDELT theme strings can be ;-separated or ,-separated; sometimes both.
        for sep in (";", ","):
            if sep in s:
                return [p.strip() for p in s.split(sep) if p.strip()]
        return [s]
    return []


def extract_themes(article_row: dict[str, Any]) -> list[str]:
    """Pull GDELT theme codes off an article row.

    GDELT DOC 2.0 article_search returns articles without GKG themes by default;
    they come from the separate GKG endpoint or from `gkg_theme` columns. We
    look for any of the column names we might see and union them.
    """
    candidates: list[str] = []
    for key in ("gkg_themes", "themes", "theme", "v2themes", "v2_themes"):
        candidates.extend(_split_themes(article_row.get(key)))
    # De-duplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for theme in candidates:
        normalized = theme.upper().strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def aggregate_themes(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Count theme codes across a batch of articles."""
    counter: Counter[str] = Counter()
    for row in rows:
        for theme in extract_themes(row):
            counter[theme] += 1
    return dict(counter)


@lru_cache(maxsize=1)
def load_theme_labels(path: Path | None = None) -> dict[str, dict[str, str]]:
    """Load the GDELT theme code -> human label mapping (cached)."""
    target = path or DEFAULT_LABELS_PATH
    if not target.exists():
        logger.warning("theme_labels.json not found at %s — labels will be empty.", target)
        return {}
    with target.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("themes", {})


def label_for(code: str) -> str:
    """Return the human-readable label for a GDELT theme code (or the code itself)."""
    if not code:
        return ""
    labels = load_theme_labels()
    entry = labels.get(code)
    if entry:
        return entry.get("label", code)
    return code


__all__ = [
    "extract_themes",
    "aggregate_themes",
    "load_theme_labels",
    "label_for",
]

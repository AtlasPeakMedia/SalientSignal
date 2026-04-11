"""GDELT theme tag extraction + label lookup.

**Session 31 architectural note — READ BEFORE USING extract_themes()**

`extract_themes()` was designed for a GDELT DOC 2.0 API response that
includes per-article theme tags. It turns out that API mode does NOT exist:
`ArtList` returns only `url, url_mobile, title, seendate, socialimage,
domain, language, sourcecountry` — no themes, no GKG fields. And the
"wordcloud themes" modes (`wordcloudthemes`, `wordcloudenglishthemes`)
return "Invalid mode" when queried. This was discovered during session 31
when we noticed all 118 articles in Supabase had `gdelt_themes=[]`.

As a result, `extract_themes()` called on any real GDELT DOC 2.0 ArtList
row will silently return an empty list — the fields it looks for
(`gkg_themes`, `themes`, `v2themes`, etc.) simply don't exist in the
response. This is a known dead code path kept in place so the existing
pipeline doesn't crash, but NEW theme ingestion should go through the
GKG 2.0 bulk client instead:

    from pipeline.src.gkg_client import fetch_gkg_file, GkgRow
    from pipeline.src.theme_aggregator import aggregate_themes  # NOT this module's

The `label_for()` function in THIS module is still used by the frontend
and by both GKG and DOC-era pipelines to turn GDELT theme codes like
`ARMEDCONFLICT` into human-readable labels. That part is fine.

Public surface:

    extract_themes(article_row)         — legacy, returns [] for DOC 2.0 rows
    aggregate_themes(rows)               — legacy counter, works on any rows
                                            BUT prefer theme_aggregator.aggregate_themes
                                            (which understands the GkgRow dataclass)
    load_theme_labels()                  — read pipeline/data/theme_labels.json
    label_for(code)                      — human-readable label for a code
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
    """**LEGACY** — returns [] for any real GDELT DOC 2.0 ArtList row.

    The DOC 2.0 API doesn't actually return theme data in ArtList mode
    (confirmed session 31). This function is kept for backward compat with
    the existing pipeline code path and will correctly extract themes if
    a row happens to have a `gkg_themes` / `themes` / `v2themes` field,
    but that never happens for live GDELT responses.

    For live theme ingestion, use pipeline.src.gkg_client.fetch_gkg_file()
    which reads GDELT GKG 2.0 bulk CSV files from the separate CDN at
    data.gdeltproject.org/gdeltv2/. Those files DO contain per-article
    V1Themes and V2Themes columns.
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

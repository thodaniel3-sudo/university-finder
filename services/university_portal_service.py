"""
University portal source service.

Uses Brave to find OFFICIAL university pages (`.edu`, `.ac.uk`, `.edu.de`,
etc.) that are specifically about programmes, admissions, scholarships,
and tuition.

This is a SEPARATE source from the general web search. It uses its own
Brave query with university-specific operators, so results are focused
on university content only.

Cost:
  - One Brave call per cache miss (count=20).
  - Second call only if the primary query returned fewer than 8 items.
  - Cache TTL: 15 minutes (shared with the parent search_service cache).
"""

from __future__ import annotations

import threading
import time
from typing import Any
from urllib.parse import urlparse

from services.web_search_service import is_web_search_available, search_web


BRAVE_PAGE_SIZE = 20
BRAVE_DELAY_S = 1.2
SECOND_CALL_THRESHOLD = 8

# Shared with search_service.py; declared here so this module works alone.
_LAST_BRAVE_CALL = [0.0]
_BRAVE_LOCK = threading.Lock()


# ============================================================
# Rate-limited Brave wrapper (duplicated from search_service on purpose;
# keeps each service self-contained)
# ============================================================

def _brave_call(query: str, count: int = BRAVE_PAGE_SIZE) -> list[dict]:
    if not is_web_search_available():
        return []

    with _BRAVE_LOCK:
        now = time.time()
        elapsed = now - _LAST_BRAVE_CALL[0]
        if elapsed < BRAVE_DELAY_S:
            time.sleep(BRAVE_DELAY_S - elapsed)
        _LAST_BRAVE_CALL[0] = time.time()

    count = max(1, min(int(count), BRAVE_PAGE_SIZE))
    return search_web(query, count=count, offset=0)


# ============================================================
# Domain heuristics
# ============================================================

_UNIVERSITY_SUFFIXES = (
    ".edu", ".ac.uk", ".ac.jp", ".edu.au", ".edu.cn",
    ".edu.sg", ".ac.nz", ".edu.hk", ".ac.in",
    ".uni-", ".university",
)


def _is_university_domain(url: str) -> bool:
    try:
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        return False
    if not host:
        return False
    for suffix in _UNIVERSITY_SUFFIXES:
        if suffix.startswith("."):
            if host.endswith(suffix):
                return True
        else:
            if suffix in host:
                return True
    return False


def _domain_of(url: str) -> str:
    try:
        host = (urlparse(url).netloc or "").lower()
        return host.replace("www.", "")
    except Exception:
        return ""


_PAGE_TYPE_HINTS = {
    "admission": ("admission", "apply", "application", "entry-requirement"),
    "scholarship": ("scholarship", "funding", "financial-aid", "bursary", "grant"),
    "tuition": ("tuition", "fees", "cost", "semester-contribution"),
    "programme": ("programme", "program", "degree", "course", "master",
                  "bachelor", "msc", "bsc", "phd"),
    "contact": ("contact", "admissions-office"),
}


def _classify_page(rec: dict) -> str:
    haystack = ((rec.get("title") or "") + " " + (rec.get("url") or "")).lower()
    for page_type, hints in _PAGE_TYPE_HINTS.items():
        if any(h in haystack for h in hints):
            return page_type
    return "other"


def _normalize(rec: dict) -> dict[str, Any]:
    url = rec.get("url") or ""
    return {
        "title": rec.get("title") or "",
        "url": url,
        "description": rec.get("description") or "",
        "source": _domain_of(url),
        "source_type": "university_official" if _is_university_domain(url)
                       else "university_web",
        "page_type": _classify_page(rec),
    }


# ============================================================
# Main entry point
# ============================================================

def search_university_portals(query: str) -> list[dict]:
    """
    Search university portals for the given query.

    Uses a university-biased Brave query. Returns at most ~40 items
    (2 Brave calls of 20 each in the worst case).
    """
    if not query or not query.strip():
        return []

    query = query.strip()

    # Primary: site-restricted query.
    primary = _brave_call(
        f"{query} site:edu OR site:ac.uk OR site:ac.de",
        count=BRAVE_PAGE_SIZE,
    )

    # Secondary: only if the primary was thin.
    if len(primary) < SECOND_CALL_THRESHOLD:
        secondary = _brave_call(
            f"{query} university programme admission",
            count=BRAVE_PAGE_SIZE,
        )
        seen = {r.get("url") for r in primary}
        for r in secondary:
            if r.get("url") not in seen:
                primary.append(r)
                seen.add(r.get("url"))

    # Normalize and keep only those that look like university pages.
    normalized = [_normalize(r) for r in primary]
    return [r for r in normalized if r["source_type"] == "university_official"]
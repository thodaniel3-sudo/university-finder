"""
Extra sources service — Scholarships, Research, Universities, Programmes.

All four sources live in ONE file (as requested).
Each is isolated so a failure in one never breaks the others.

Sources:
  1. Scholarships  — Brave Search (site:scholarships.com, fastweb.com, etc.)
  2. Research      — OpenAlex API (free, no key required)
  3. Universities  — Brave Search (site:.edu, .ac.uk, topuniversities, etc.)
  4. Programmes    — Brave Search (site:mastersportal, bachelorsportal, daad, etc.)

Safety:
  - In-memory cache, TTL 30 minutes per source.
  - Rate limiter: 1 second minimum between outbound calls per source.
  - If the Brave key is missing, all Brave-backed sources return [].
"""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx

from config import Config


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------

OPENALEX_URL = "https://api.openalex.org/works"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"

CACHE_TTL_S = 1800            # 30 minutes
RATE_LIMIT_S = 1.0
HTTP_TIMEOUT = 20.0
USER_AGENT = "university-finder/1.0 (educational, non-commercial)"

# Which sites to search for each source
SCHOLARSHIP_SITES = [
    "scholarships.com",
    "fastweb.com",
    "collegeboard.org",
    "scholarshipportal.com",
    "chevening.org",
    "daad.de",
]

UNIVERSITY_SITES = [
    "topuniversities.com",
    "timeshighereducation.com",
    "shanghairanking.com",
    "4icu.org",
    "wikipedia.org",
]

PROGRAMME_SITES = [
    "mastersportal.com",
    "bachelorsportal.com",
    "phdportal.com",
    "daad.de",
    "studyportals.com",
    "findamasters.com",
]


# ------------------------------------------------------------
# Shared cache + rate limiter
# ------------------------------------------------------------

_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_LOCK = threading.Lock()

_LAST_CALL = {"brave": 0.0, "openalex": 0.0}
_CALL_LOCK = threading.Lock()


def _cache_get(key: str) -> list[dict] | None:
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        expires_at, payload = entry
        if expires_at < time.time():
            _CACHE.pop(key, None)
            return None
        return payload


def _cache_put(key: str, payload: list[dict]) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = (time.time() + CACHE_TTL_S, payload)
        if len(_CACHE) > 300:
            now = time.time()
            for k in list(_CACHE.keys()):
                if _CACHE[k][0] < now:
                    _CACHE.pop(k, None)


def _rate_limit(bucket: str) -> None:
    with _CALL_LOCK:
        now = time.time()
        elapsed = now - _LAST_CALL.get(bucket, 0.0)
        if elapsed < RATE_LIMIT_S:
            time.sleep(RATE_LIMIT_S - elapsed)
        _LAST_CALL[bucket] = time.time()


def _brave_key() -> str:
    return (getattr(Config, "BRAVE_SEARCH_API_KEY", "") or "").strip()


# ============================================================
# Shared Brave Search helper
# ============================================================

def _brave_search(query: str, count: int = 20) -> list[dict]:
    """
    Raw Brave web search. Returns a list of raw result dicts
    with keys: title, url, description.
    """
    if not _brave_key():
        return []

    _rate_limit("brave")

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": _brave_key(),
        "User-Agent": USER_AGENT,
    }
    params = {
        "q": query,
        "count": min(max(1, int(count)), 20),
        "safesearch": "moderate",
        "text_decorations": "false",
    }

    try:
        response = httpx.get(
            BRAVE_URL,
            params=params,
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
    except Exception as exc:
        print(f"[brave] request failed: {exc}")
        return []

    if response.status_code != 200:
        print(
            f"[brave] returned {response.status_code}: "
            f"{response.text[:200]}"
        )
        return []

    try:
        payload = response.json()
    except Exception:
        return []

    web = payload.get("web") or {}
    results = web.get("results") or []
    if not isinstance(results, list):
        return []

    cleaned: list[dict] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        url = r.get("url") or ""
        if not url:
            continue
        cleaned.append({
            "title": r.get("title") or "",
            "url": url,
            "description": r.get("description") or "",
        })
    return cleaned


def _brave_multi_query(
    base_query: str,
    sites: list[str],
    per_site: int = 5,
) -> list[dict]:
    """
    Run one Brave query per site and combine results.
    Each site contributes up to `per_site` results.
    """
    combined: list[dict] = []
    seen_urls: set[str] = set()

    for site in sites:
        q = f"{base_query} site:{site}"
        for item in _brave_search(q, count=per_site):
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            item["_site"] = site
            combined.append(item)

    return combined


# ============================================================
# SOURCE 1 — SCHOLARSHIPS (Brave)
# ============================================================

def is_scholarships_available() -> bool:
    return bool(_brave_key())


def _normalize_scholarship(item: dict) -> dict[str, Any]:
    return {
        "id": item.get("url") or item.get("title") or "",
        "title": item.get("title") or "Scholarship",
        "provider": item.get("_site") or "",
        "amount": "",
        "deadline": "",
        "description": (item.get("description") or "")[:500],
        "url": item.get("url") or "",
        "source_url": item.get("url") or "",
        "eligibility": "",
        "source_type": "scholarship",
    }


def search_scholarships(query: str, limit: int = 25) -> list[dict]:
    query = (query or "").strip()
    if not query or not is_scholarships_available():
        return []

    key = f"scholarship::{query.lower()}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    # Focus the query toward funding
    focused = f"{query} scholarship funding for students"
    raw = _brave_multi_query(focused, SCHOLARSHIP_SITES, per_site=5)

    normalized = [_normalize_scholarship(x) for x in raw][:limit]
    if normalized:
        _cache_put(key, normalized)
        print(f"[scholarships] Brave returned {len(normalized)} results")
    else:
        print("[scholarships] Brave returned no results")
    return normalized


# ============================================================
# SOURCE 2 — RESEARCH (OpenAlex, unchanged)
# ============================================================

def is_research_available() -> bool:
    return True


def _normalize_work(item: dict) -> dict[str, Any]:
    authors = item.get("authorships") or []
    author_names = []
    for a in authors[:4]:
        name = ((a.get("author") or {}).get("display_name")) or ""
        if name:
            author_names.append(name)
    author_str = ", ".join(author_names)
    if len(authors) > 4:
        author_str += ", et al."

    host = (item.get("primary_location") or {}).get("source") or {}
    venue = host.get("display_name") or ""

    abstract = item.get("abstract_inverted_index")
    abstract_text = ""
    if isinstance(abstract, dict):
        words: dict[int, str] = {}
        for word, positions in abstract.items():
            for p in positions:
                words[p] = word
        abstract_text = " ".join(words[i] for i in sorted(words.keys()))
        if len(abstract_text) > 500:
            abstract_text = abstract_text[:500] + "…"

    return {
        "id": (item.get("id") or "").replace("https://openalex.org/", ""),
        "title": item.get("display_name") or "Untitled",
        "authors": author_str,
        "venue": venue,
        "year": item.get("publication_year") or "",
        "cited_by": item.get("cited_by_count") or 0,
        "doi": item.get("doi") or "",
        "url": item.get("doi") or item.get("id") or "",
        "source_url": item.get("doi") or item.get("id") or "",
        "description": abstract_text,
        "source_type": "research",
    }


def search_research(query: str, limit: int = 20) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []

    key = f"research::{query.lower()}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    _rate_limit("openalex")

    params = {
        "search": query,
        "per-page": min(max(1, int(limit)), 50),
        "sort": "relevance_score:desc",
        "mailto": "university-finder@example.com",
    }

    try:
        response = httpx.get(
            OPENALEX_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
    except Exception as exc:
        print(f"[research] request failed: {exc}")
        return []

    if response.status_code != 200:
        print(f"[research] returned {response.status_code}: {response.text[:200]}")
        return []

    try:
        payload = response.json()
    except Exception:
        return []

    results = payload.get("results") or []
    normalized = [_normalize_work(x) for x in results if isinstance(x, dict)]
    _cache_put(key, normalized)
    return normalized


# ============================================================
# SOURCE 3 — UNIVERSITIES (Brave)
# ============================================================

def is_universities_available() -> bool:
    return bool(_brave_key())


def _normalize_university(item: dict) -> dict[str, Any]:
    return {
        "id": item.get("url") or item.get("title") or "",
        "title": item.get("title") or "University",
        "country": "",
        "alpha_two_code": "",
        "domain": item.get("_site") or "",
        "url": item.get("url") or "",
        "source_url": item.get("url") or "",
        "description": (item.get("description") or "")[:500],
        "source_type": "university_directory",
    }


def search_universities(query: str, limit: int = 25) -> list[dict]:
    query = (query or "").strip()
    if not query or not is_universities_available():
        return []

    key = f"university::{query.lower()}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    focused = f"{query} university ranking top universities"
    raw = _brave_multi_query(focused, UNIVERSITY_SITES, per_site=5)

    normalized = [_normalize_university(x) for x in raw][:limit]
    if normalized:
        _cache_put(key, normalized)
        print(f"[universities] Brave returned {len(normalized)} results")
    else:
        print("[universities] Brave returned no results")
    return normalized


# ============================================================
# SOURCE 4 — PROGRAMMES (Brave)
# ============================================================

def is_programmes_available() -> bool:
    return bool(_brave_key())


def _normalize_programme(item: dict) -> dict[str, Any]:
    return {
        "id": item.get("url") or item.get("title") or "",
        "title": item.get("title") or "Programme",
        "provider": item.get("_site") or "",
        "level": "",
        "duration": "",
        "description": (item.get("description") or "")[:500],
        "url": item.get("url") or "",
        "source_url": item.get("url") or "",
        "source_type": "programme",
    }


def search_programmes(query: str, limit: int = 25) -> list[dict]:
    query = (query or "").strip()
    if not query or not is_programmes_available():
        return []

    key = f"programme::{query.lower()}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    focused = f"{query} degree programme master bachelor phd"
    raw = _brave_multi_query(focused, PROGRAMME_SITES, per_site=5)

    normalized = [_normalize_programme(x) for x in raw][:limit]
    if normalized:
        _cache_put(key, normalized)
        print(f"[programmes] Brave returned {len(normalized)} results")
    else:
        print("[programmes] Brave returned no results")
    return normalized


# ============================================================
# Availability summary
# ============================================================

def source_availability() -> dict[str, bool]:
    return {
        "scholarships": is_scholarships_available(),
        "research": is_research_available(),
        "universities": is_universities_available(),
        "programmes": is_programmes_available(),
    }
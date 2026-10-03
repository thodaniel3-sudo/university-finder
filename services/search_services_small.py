"""
Search orchestration - database + Brave web + university portals.

BRAVE QUOTA OPTIMIZATION:

  Brave's free tier is 2,000 queries/month and 1 query/second. A naive
  implementation fires 10 requests per search, which exhausts the quota
  after ~200 searches. This module is built to be frugal:

  1. ONE request per source, using count=20 (Brave's free-tier maximum).
  2. In-memory response cache, keyed on the normalized query, TTL 15 min.
     The same query inside the TTL costs zero Brave requests.
  3. If the local database already returned >= SKIP_WEB_DB_THRESHOLD
     results, we skip Brave entirely. The user's query is well covered.
  4. The university-portal source is derived by FILTERING the web results
     for university-like domains. No second Brave request.

Typical cost:
  - Cache hit              -> 0 Brave requests
  - DB-heavy query         -> 0 Brave requests
  - Cache miss, DB-thin    -> 1 Brave request  (web + university together)
  - Absolute worst case    -> 2 Brave requests (web, then university if
                             the first request returned almost nothing)
"""

import threading
import time
from typing import Any
from urllib.parse import urlparse

from services.supabase_service import get_public_client
from services.web_search_service import is_web_search_available, search_web


DEFAULT_PER_PAGE = 20
BRAVE_PAGE_SIZE = 20          # free-tier max; do not exceed
BRAVE_DELAY_S = 1.2           # min gap between consecutive Brave calls

# If the DB returns this many results, do not query Brave at all.
SKIP_WEB_DB_THRESHOLD = 5

# In-memory cache: {query_key: (expires_at_epoch, payload)}
_CACHE_TTL_S = 900            # 15 minutes
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_LOCK = threading.Lock()

# Rate-limit lock: ensures we never call Brave twice within BRAVE_DELAY_S.
_LAST_BRAVE_CALL = [0.0]
_BRAVE_LOCK = threading.Lock()


# ============================================================
# Cache helpers
# ============================================================

def _cache_key(query: str) -> str:
    return (query or "").strip().lower()


def _cache_get(key: str) -> dict | None:
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        expires_at, payload = entry
        if expires_at < time.time():
            _CACHE.pop(key, None)
            return None
        return payload


def _cache_put(key: str, payload: dict) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = (time.time() + _CACHE_TTL_S, payload)
        # Keep the cache small — drop anything older than TTL.
        if len(_CACHE) > 200:
            now = time.time()
            for k in list(_CACHE.keys()):
                if _CACHE[k][0] < now:
                    _CACHE.pop(k, None)


# ============================================================
# Rate-limited Brave wrapper
# ============================================================

def _brave_call(query: str, count: int = BRAVE_PAGE_SIZE) -> list[dict]:
    """
    Call Brave once, honoring the 1 request/second rate limit.
    Returns [] if Brave is not available or the call fails.
    """
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
# Database search
# ============================================================

def _search_db_programmes(query: str, limit: int, offset: int) -> tuple[list[dict], int]:
    client = get_public_client()
    pattern = f"%{query}%"
    seen_ids: set[int] = set()
    all_rows: list[dict] = []

    for column in ("programme_name", "field", "specialization"):
        try:
            response = (
                client.table("programmes")
                .select(
                    "id, programme_name, degree_level, field, specialization, "
                    "study_mode, duration, language, "
                    "universities(id, name, country, city)"
                )
                .ilike(column, pattern)
                .eq("status", "active")
                .order("programme_name")
                .execute()
            )
        except Exception:
            continue

        for row in response.data or []:
            rid = row["id"]
            if rid not in seen_ids:
                seen_ids.add(rid)
                all_rows.append(row)

    total = len(all_rows)
    page_rows = all_rows[offset:offset + limit]
    return page_rows, total


def _search_db_universities(query: str, limit: int, offset: int) -> tuple[list[dict], int]:
    client = get_public_client()
    pattern = f"%{query}%"
    seen_ids: set[int] = set()
    all_rows: list[dict] = []

    for column in ("name", "city", "country"):
        try:
            response = (
                client.table("universities")
                .select("id, name, country, city, website_url, status")
                .ilike(column, pattern)
                .eq("status", "active")
                .order("name")
                .execute()
            )
        except Exception:
            continue

        for row in response.data or []:
            rid = row["id"]
            if rid not in seen_ids:
                seen_ids.add(rid)
                all_rows.append(row)

    total = len(all_rows)
    page_rows = all_rows[offset:offset + limit]
    return page_rows, total


# ============================================================
# University domain filter (runs on web results, no Brave cost)
# ============================================================

def _is_university_domain(url: str) -> bool:
    try:
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        return False
    if not host:
        return False
    if host.endswith(".edu") or host.endswith(".ac.uk"):
        return True
    if host.endswith(".ac.jp") or host.endswith(".edu.au"):
        return True
    if host.endswith(".edu.cn"):
        return True
    if ".uni-" in host or host.startswith("uni-"):
        return True
    return False


def _partition_university(web_results: list[dict]) -> list[dict]:
    """Split web results into university-portal results (no Brave cost)."""
    out: list[dict] = []
    for r in web_results:
        url = r.get("url") or ""
        if _is_university_domain(url):
            out.append({
                "title": r.get("title") or "",
                "url": url,
                "description": r.get("description") or "",
                "source": r.get("source") or "",
                "source_type": "university_official",
            })
    return out


# ============================================================
# Top-level
# ============================================================

def search_everything(
    query: str,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> dict[str, Any]:
    query = (query or "").strip()
    page = max(1, int(page or 1))
    offset = (page - 1) * per_page
    web_available = is_web_search_available()

    empty = {
        "query": "",
        "db_programmes": [],
        "db_universities": [],
        "db_total": 0,
        "db_programme_total": 0,
        "db_university_total": 0,
        "db_page": 1,
        "db_per_page": per_page,
        "db_total_pages": 1,
        "web_results": [],
        "web_available": web_available,
        "web_offset": 0,
        "has_more_web": False,
        "university_results": [],
        "university_available": web_available,
    }

    if not query:
        return empty

    # ---- Database (always free) ----
    db_programmes, prog_total = _search_db_programmes(query, per_page, offset)
    db_universities, uni_total = _search_db_universities(query, per_page, offset)

    db_total = prog_total + uni_total
    max_per_set = max(prog_total, uni_total)
    db_total_pages = max(1, (max_per_set + per_page - 1) // per_page)

    # ---- Cache lookup for the Brave-backed part ----
    cache_key = _cache_key(query)
    cached = _cache_get(cache_key)

    if cached is not None:
        web_results = cached["web_results"]
        university_results = cached["university_results"]
    elif db_total >= SKIP_WEB_DB_THRESHOLD:
        # DB already covers the query well. Skip Brave to save quota.
        web_results = []
        university_results = []
        _cache_put(cache_key, {
            "web_results": web_results,
            "university_results": university_results,
        })
    elif not web_available:
        web_results = []
        university_results = []
    else:
        # Single Brave request. Filter the same result set for university
        # domains so we do not pay for a second query.
        raw = _brave_call(f"{query} master programme university",
                          count=BRAVE_PAGE_SIZE)
        university_results = _partition_university(raw)
        # Non-university results become the "web" section.
        university_urls = {r["url"] for r in university_results}
        web_results = [r for r in raw if r.get("url") not in university_urls]

        _cache_put(cache_key, {
            "web_results": web_results,
            "university_results": university_results,
        })

    return {
        "query": query,
        "db_programmes": db_programmes,
        "db_universities": db_universities,
        "db_total": db_total,
        "db_programme_total": prog_total,
        "db_university_total": uni_total,
        "db_page": page,
        "db_per_page": per_page,
        "db_total_pages": db_total_pages,
        "web_results": web_results,
        "web_available": web_available,
        "web_offset": offset,
        "has_more_web": False,
        "university_results": university_results,
        "university_available": web_available,
    }
"""
Search orchestration - database + Brave web + university portals +
Facebook + YouTube + shared discovery catalog.

ARCHITECTURE:
  - Supabase DB                : 0 Brave calls
  - Shared discovery catalog   : 0 Brave calls (grows with user saves)
  - Brave Web                  : 1-2 Brave calls (broad query)
  - University portals         : 1-2 Brave calls (site-restricted query)
  - Facebook                   : 0 Brave calls (OAuth-sourced via session)
  - YouTube                    : 1 YouTube quota unit (separate quota)

Total Brave cost per cold search: 2-4 requests. Cache hits cost 0.
YouTube has its own quota: 100 search.list calls/day.

CACHE:
  In-memory, keyed on the normalized query, TTL 15 minutes.
  Shared by all Brave-backed sources.
  YouTube has its own cache inside youtube_service.
"""

import threading
import time
from typing import Any
from urllib.parse import urlparse

from services.discovery_service import search_discoveries
from services.supabase_service import get_public_client
from services.web_search_service import is_web_search_available, search_web
from services.university_portal_service import search_university_portals
from services.youtube_service import search_youtube


DEFAULT_PER_PAGE = 20
BRAVE_PAGE_SIZE = 20
BRAVE_DELAY_S = 1.2
SECOND_CALL_THRESHOLD = 8

_CACHE_TTL_S = 900
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_LOCK = threading.Lock()

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
        if len(_CACHE) > 200:
            now = time.time()
            for k in list(_CACHE.keys()):
                if _CACHE[k][0] < now:
                    _CACHE.pop(k, None)


# ============================================================
# Rate-limited Brave wrapper
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


def _brave_fetch_web(query: str) -> list[dict]:
    """Fetch web results. Secondary call only if primary was thin."""
    primary = _brave_call(query, count=BRAVE_PAGE_SIZE)
    if len(primary) >= SECOND_CALL_THRESHOLD:
        return primary

    secondary = _brave_call(
        f"{query} master programme university",
        count=BRAVE_PAGE_SIZE,
    )
    seen = {r.get("url") for r in primary}
    for r in secondary:
        if r.get("url") not in seen:
            primary.append(r)
            seen.add(r.get("url"))
    return primary


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
# University domain filter
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


# ============================================================
# Facebook source (session-scoped, no Brave cost)
# ============================================================

def _facebook_results_if_connected(query: str) -> dict:
    """
    Read the current user's Facebook session and, if connected, fetch
    recent posts from the Pages they administer, filtered by the query.
    """
    try:
        from flask import session as flask_session
        from services.facebook_service import search_facebook

        user_token = flask_session.get("facebook_user_token")
        pages = flask_session.get("facebook_pages") or []

        if not user_token:
            return {"connected": False, "pages_count": 0, "results": []}

        raw = search_facebook(
            user_token=user_token,
            query=query,
            max_pages=10,
            posts_per_page=25,
        )

        normalized = []
        for r in raw:
            normalized.append({
                "title": r.get("title") or "",
                "organization": r.get("organization") or r.get("page_name") or "",
                "description": r.get("description") or r.get("message") or "",
                "source_url": r.get("source_url") or r.get("permalink_url") or "",
                "source_type": "facebook",
                "published_at": r.get("created_time") or "",
                "page_name": r.get("page_name") or "",
            })

        return {
            "connected": True,
            "pages_count": len(pages),
            "results": normalized,
        }
    except Exception:
        return {"connected": False, "pages_count": 0, "results": []}


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
        "facebook_connected": False,
        "facebook_pages_count": 0,
        "facebook_results": [],
        "youtube_results": [],
        "discovery_results": [],
    }

    if not query:
        return empty

    # ---- Shared discovery catalog (free, grows with user saves) ----
    try:
        discovery_results = search_discoveries(query, limit=20)
    except Exception:
        discovery_results = []

    # ---- Database (always free) ----
    db_programmes, prog_total = _search_db_programmes(query, per_page, offset)
    db_universities, uni_total = _search_db_universities(query, per_page, offset)

    db_total = prog_total + uni_total
    max_per_set = max(prog_total, uni_total)
    db_total_pages = max(1, (max_per_set + per_page - 1) // per_page)

    # ---- Brave-backed sources (cache first) ----
    cache_key = _cache_key(query)
    cached = _cache_get(cache_key)

    if cached is not None:
        web_results = cached["web_results"]
        university_results = cached["university_results"]
    elif not web_available:
        web_results = []
        university_results = []
    else:
        raw_web = _brave_fetch_web(query)
        web_results = [
            {
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "description": r.get("description") or "",
                "source": r.get("source") or "",
            }
            for r in raw_web
            if not _is_university_domain(r.get("url") or "")
        ]
        university_results = search_university_portals(query)

        _cache_put(cache_key, {
            "web_results": web_results,
            "university_results": university_results,
        })

    # ---- Facebook (session-scoped, always fresh, no cache) ----
    fb = _facebook_results_if_connected(query)

    # ---- YouTube (separate quota; cached inside youtube_service) ----
    youtube_results = search_youtube(query) if query else []

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
        "facebook_connected": fb["connected"],
        "facebook_pages_count": fb["pages_count"],
        "facebook_results": fb["results"],
        "youtube_results": youtube_results,
        "discovery_results": discovery_results,
    }
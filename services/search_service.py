"""
Search orchestration: database + Brave web + university portals.

Brave's free tier caps each request at 20 results. To reach ~100 per source
we loop through multiple pages of 20, with a small delay between calls.
"""

import time
from typing import Any
from urllib.parse import urlparse

from services.supabase_service import get_public_client
from services.web_search_service import is_web_search_available, search_web


DEFAULT_PER_PAGE = 20
BRAVE_PAGE_SIZE = 20      # free tier hard cap
BRAVE_MAX_PAGES = 5       # 5 x 20 = up to 100 results per source
BRAVE_DELAY_S = 1.2       # stay under the 1 req/sec limit


# ============================================================
# Brave paginated fetch
# ============================================================

def _brave_fetch_all(query: str, max_pages: int = BRAVE_MAX_PAGES) -> list[dict]:
    """
    Fetch up to max_pages * BRAVE_PAGE_SIZE results from Brave,
    one page at a time. Stops early if a page returns fewer than
    BRAVE_PAGE_SIZE results (means we exhausted the index).

    Every request uses count=BRAVE_PAGE_SIZE (20) so the free tier
    never rejects it.
    """
    all_results: list[dict] = []
    for page_index in range(max_pages):
        offset = page_index * BRAVE_PAGE_SIZE
        if offset >= 200:
            break

        page = search_web(
            query,
            count=BRAVE_PAGE_SIZE,
            offset=offset,
        )
        if not page:
            break

        all_results.extend(page)

        if len(page) < BRAVE_PAGE_SIZE:
            # Brave returned fewer than requested → no more results.
            break

        # Be polite: stay under the 1 request/second rate limit.
        time.sleep(BRAVE_DELAY_S)

    return all_results


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
# University portal search
# ============================================================

_UNIVERSITY_DOMAIN_HINTS = (
    ".edu",
    ".ac.uk",
    ".ac.jp",
    ".edu.au",
    ".edu.cn",
    ".uni-",
)


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


def _search_university_portals(query: str) -> list[dict]:
    """
    Use Brave (paginated) to find official university pages about the query.
    """
    if not is_web_search_available():
        return []

    portal_query = f"{query} site:edu OR site:ac.uk OR university programme admissions"
    raw = _brave_fetch_all(portal_query)

    out: list[dict] = []
    for r in raw:
        url = r.get("url") or ""
        out.append({
            "title": r.get("title") or "",
            "url": url,
            "description": r.get("description") or "",
            "source": r.get("source") or "",
            "source_type": (
                "university_official" if _is_university_domain(url)
                else "university_web"
            ),
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

    if not query:
        return {
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

    # ---- DB ----
    db_programmes, prog_total = _search_db_programmes(query, per_page, offset)
    db_universities, uni_total = _search_db_universities(query, per_page, offset)

    db_total = prog_total + uni_total
    max_per_set = max(prog_total, uni_total)
    db_total_pages = max(1, (max_per_set + per_page - 1) // per_page)

    # ---- Web (Brave, paginated) ----
    web_results: list[dict] = []
    has_more_web = False

    if web_available and page == 1:
        web_query = f"{query} master programme university"
        web_results = _brave_fetch_all(web_query)
        has_more_web = len(web_results) >= (BRAVE_PAGE_SIZE * BRAVE_MAX_PAGES)

    # ---- University portals (Brave, paginated) ----
    university_results: list[dict] = []
    if web_available and page == 1:
        university_results = _search_university_portals(query)

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
        "has_more_web": has_more_web,
        "university_results": university_results,
        "university_available": web_available,
    }
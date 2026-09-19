"""
Search orchestration: query the database first, optionally augment with web.

Public API:
    search_everything(query, page=1, per_page=20) -> {
        "db_universities": [...],
        "db_programmes": [...],
        "db_total": int,
        "db_page": int,
        "db_per_page": int,
        "db_total_pages": int,
        "web_results": [...],
        "web_available": bool,
        "web_page": int,
        "web_offset": int,
        "has_more_web": bool,
    }
"""

from typing import Any

from services.supabase_service import get_public_client
from services.web_search_service import is_web_search_available, search_web


DEFAULT_PER_PAGE = 20
WEB_PER_PAGE = 20


# ============================================================
# Database search — paginated
# ============================================================

def _search_db_programmes(query: str, limit: int, offset: int) -> tuple[list[dict], int]:
    """
    Search programmes by name/field/specialization.

    Returns (rows, total_count). `total_count` is a best-effort estimate
    because we search three columns — we may over-count if a row matches
    multiple columns, so we deduplicate.
    """
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
    """Search universities by name/city/country. Returns (rows, total_count)."""
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
# Top-level
# ============================================================

def search_everything(
    query: str,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> dict[str, Any]:
    """
    Return DB + web results for one page.

    DB results are paginated internally.
    Web results are fetched with an offset matching the page.
    """
    query = (query or "").strip()

    page = max(1, int(page or 1))
    offset = (page - 1) * per_page

    if not query:
        return {
            "query": "",
            "db_programmes": [],
            "db_universities": [],
            "db_total": 0,
            "db_page": 1,
            "db_per_page": per_page,
            "db_total_pages": 1,
            "web_results": [],
            "web_available": is_web_search_available(),
            "web_page": page,
            "web_offset": 0,
            "has_more_web": False,
        }

    # ---- DB search (paginated) ----
    db_programmes, prog_total = _search_db_programmes(query, per_page, offset)
    db_universities, uni_total = _search_db_universities(query, per_page, offset)

    db_total = prog_total + uni_total
    db_total_pages = max(1, (max(prog_total, uni_total) + per_page - 1) // per_page)

    # ---- Web search (same page) ----
    web_results: list[dict] = []
    web_available = is_web_search_available()
    has_more_web = False

    if web_available:
        # Only search the web if the DB is thin OR the user is on page 1.
        # For page 2+, most users are browsing DB results — skip the API
        # call to preserve quota.
        should_hit_web = (db_total < 5) or (page == 1)

        if should_hit_web:
            web_query = f"{query} master programme university"
            web_results = search_web(
                web_query,
                count=WEB_PER_PAGE,
                offset=offset,
            )
            has_more_web = len(web_results) >= WEB_PER_PAGE

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
        "web_page": page,
        "web_offset": offset,
        "has_more_web": has_more_web,
    }
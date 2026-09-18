"""
Search orchestration: query the database first, fall back to the web.

Public API:
    search_everything(query) -> {
        "db_universities": [...],
        "db_programmes": [...],
        "web_results": [...],
        "web_available": bool,
    }
"""

from typing import Any

from services.supabase_service import get_public_client
from services.web_search_service import is_web_search_available, search_web


DB_RESULT_LIMIT = 10


def _search_db_programmes(query: str, limit: int) -> list[dict[str, Any]]:
    """
    Search programmes by name, field, and specialization using ILIKE.

    Supabase's Python client doesn't support OR natively in a single chain,
    so we run a few queries and merge results.
    """
    client = get_public_client()
    pattern = f"%{query}%"

    results: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

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
                .limit(limit)
                .execute()
            )
        except Exception:
            continue

        for row in response.data or []:
            if row["id"] not in seen_ids:
                seen_ids.add(row["id"])
                results.append(row)
                if len(results) >= limit:
                    return results

    return results


def _search_db_universities(query: str, limit: int) -> list[dict[str, Any]]:
    """Search universities by name and city."""
    client = get_public_client()
    pattern = f"%{query}%"

    results: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    for column in ("name", "city", "country"):
        try:
            response = (
                client.table("universities")
                .select("id, name, country, city, website_url, status")
                .ilike(column, pattern)
                .eq("status", "active")
                .limit(limit)
                .execute()
            )
        except Exception:
            continue

        for row in response.data or []:
            if row["id"] not in seen_ids:
                seen_ids.add(row["id"])
                results.append(row)
                if len(results) >= limit:
                    return results

    return results


def search_everything(query: str) -> dict[str, Any]:
    """
    Return a dict with database + web results.

    Structure:
        {
          "query": str,
          "db_universities": [ {...}, ... ],
          "db_programmes":   [ {...}, ... ],
          "web_results":     [ {...}, ... ] or [],
          "web_available":   bool,
          "db_count":        int,
          "web_count":       int,
        }
    """
    query = (query or "").strip()

    if not query:
        return {
            "query": "",
            "db_universities": [],
            "db_programmes": [],
            "web_results": [],
            "web_available": is_web_search_available(),
            "db_count": 0,
            "web_count": 0,
        }

    db_universities = _search_db_universities(query, DB_RESULT_LIMIT)
    db_programmes = _search_db_programmes(query, DB_RESULT_LIMIT)
    db_count = len(db_universities) + len(db_programmes)

    web_results: list[dict[str, Any]] = []
    web_available = is_web_search_available()

    # Only hit the web if we have the key AND no strong database match.
    # That way we don't waste quota on queries we can answer ourselves.
    if web_available and db_count < 3:
        web_query = f"{query} master programme university"
        web_results = search_web(web_query, count=8)

    return {
        "query": query,
        "db_universities": db_universities,
        "db_programmes": db_programmes,
        "web_results": web_results,
        "web_available": web_available,
        "db_count": db_count,
        "web_count": len(web_results),
    }
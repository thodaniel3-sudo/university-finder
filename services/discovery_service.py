"""
Shared discovery catalog service.

Records URLs the application has surfaced so future searches can answer
from the database instead of hitting Brave again.

Public API:
    record_discovery(payload, saved_by=None)  -> dict (upserted row)
    search_discoveries(query, limit=20)       -> list[dict]
    is_discovered(url)                        -> bool
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.supabase_service import get_admin_client


_ALLOWED_FIELDS = {
    "url", "title", "organization", "description", "source_type",
    "source_domain", "country", "city", "degree_level", "field_of_study",
    "search_query", "thumbnail_url", "extra",
}


def record_discovery(payload: dict[str, Any], saved_by: str | None = None) -> dict[str, Any]:
    """
    Insert a new discovery or bump saved_count if the URL already exists.

    Idempotent on url. Returns the row.
    """
    url = (payload.get("url") or "").strip()
    if not url:
        raise ValueError("url is required")

    clean = {k: payload.get(k) for k in _ALLOWED_FIELDS if k in payload}
    clean["url"] = url
    clean["updated_at"] = datetime.now(timezone.utc).isoformat()

    if saved_by:
        clean["saved_by"] = saved_by

    client = get_admin_client()

    existing = (
        client.table("saved_discoveries")
        .select("id, saved_count")
        .eq("url", url)
        .limit(1)
        .execute()
    )

    if existing.data:
        row = existing.data[0]
        new_count = int(row.get("saved_count") or 1) + 1
        response = (
            client.table("saved_discoveries")
            .update({"saved_count": new_count, "updated_at": clean["updated_at"]})
            .eq("id", row["id"])
            .execute()
        )
        return response.data[0] if response.data else {}

    clean["saved_count"] = 1
    response = client.table("saved_discoveries").insert(clean).execute()
    return response.data[0] if response.data else {}


def is_discovered(url: str) -> bool:
    if not url:
        return False
    client = get_admin_client()
    response = (
        client.table("saved_discoveries")
        .select("id")
        .eq("url", url)
        .limit(1)
        .execute()
    )
    return bool(response.data)


def search_discoveries(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """
    Search the shared discovery catalog.

    Runs ILIKE across title, organization, description, field_of_study,
    city, and country. Deduplicates by id. Returns normalized rows.
    """
    query = (query or "").strip()
    if not query:
        return []

    client = get_admin_client()
    pattern = f"%{query}%"

    seen: set[int] = set()
    rows: list[dict] = []

    for column in ("title", "organization", "description",
                   "field_of_study", "city", "country"):
        try:
            response = (
                client.table("saved_discoveries")
                .select("*")
                .ilike(column, pattern)
                .order("saved_count", desc=True)
                .limit(limit)
                .execute()
            )
        except Exception:
            continue

        for row in response.data or []:
            rid = row["id"]
            if rid not in seen:
                seen.add(rid)
                rows.append(row)

    out: list[dict[str, Any]] = []
    for r in rows[:limit]:
        out.append({
            "id": r.get("id"),
            "title": r.get("title") or "",
            "organization": r.get("organization") or "",
            "description": r.get("description") or "",
            "website_url": r.get("url") or "",
            "source_url": r.get("url") or "",
            "source": r.get("source_domain") or "",
            "country": r.get("country") or "",
            "city": r.get("city") or "",
            "degree_level": r.get("degree_level") or "",
            "field_of_study": r.get("field_of_study") or "",
            "source_type": r.get("source_type") or "discovery",
            "saved_count": r.get("saved_count") or 1,
            "verified": bool(r.get("verified")),
            "created_at": r.get("created_at") or "",
        })
    return out
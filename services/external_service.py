"""
Service for user-saved external (web-discovered) programmes.

Uses the USER client — RLS enforces ownership.
"""

from typing import Any

from services.supabase_service import get_user_client


ALLOWED_UPDATE_FIELDS = {"notes", "status"}


def save_external(
    user_id: str,
    access_token: str,
    *,
    title: str,
    url: str,
    source_domain: str | None = None,
    description: str | None = None,
    search_query: str | None = None,
) -> dict[str, Any]:
    """Insert a new saved external programme. Idempotent on (user, url)."""
    client = get_user_client(access_token)

    # Check if already saved by this user for this URL.
    existing = (
        client.table("saved_external_programmes")
        .select("*")
        .eq("user_id", user_id)
        .eq("url", url)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    payload = {
        "user_id": user_id,
        "title": (title or "").strip()[:500] or "(untitled)",
        "url": url,
        "source_domain": (source_domain or "").strip()[:200] or None,
        "description": (description or "").strip()[:2000] or None,
        "search_query": (search_query or "").strip()[:500] or None,
    }
    response = client.table("saved_external_programmes").insert(payload).execute()
    return response.data[0] if response.data else {}


def get_external(user_id: str, access_token: str, external_id: int) -> dict[str, Any] | None:
    client = get_user_client(access_token)
    response = (
        client.table("saved_external_programmes")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", external_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def list_external(user_id: str, access_token: str) -> list[dict[str, Any]]:
    client = get_user_client(access_token)
    response = (
        client.table("saved_external_programmes")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def update_external(
    user_id: str,
    access_token: str,
    external_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    clean = {k: v for k, v in payload.items() if k in ALLOWED_UPDATE_FIELDS}
    client = get_user_client(access_token)
    response = (
        client.table("saved_external_programmes")
        .update(clean)
        .eq("user_id", user_id)
        .eq("id", external_id)
        .execute()
    )
    return response.data[0] if response.data else {}


def delete_external(user_id: str, access_token: str, external_id: int) -> None:
    client = get_user_client(access_token)
    client.table("saved_external_programmes").delete().eq("user_id", user_id).eq("id", external_id).execute()


def is_saved_external(user_id: str, access_token: str, url: str) -> bool:
    client = get_user_client(access_token)
    response = (
        client.table("saved_external_programmes")
        .select("id")
        .eq("user_id", user_id)
        .eq("url", url)
        .limit(1)
        .execute()
    )
    return bool(response.data)


def list_saved_external_urls(user_id: str, access_token: str) -> set[str]:
    """Return set of URLs this user has already saved. For bulk UI checks."""
    client = get_user_client(access_token)
    response = (
        client.table("saved_external_programmes")
        .select("url")
        .eq("user_id", user_id)
        .execute()
    )
    return {row["url"] for row in (response.data or [])}
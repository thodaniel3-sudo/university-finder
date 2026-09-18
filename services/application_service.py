"""
Application tracker service.

All operations go through the USER client — RLS enforces ownership.
"""

from datetime import date, datetime
from typing import Any

from services.supabase_service import get_user_client


def list_applications(user_id: str, access_token: str) -> list[dict[str, Any]]:
    """
    Return the user's applications with nested programme and university.
    Ordered by most recently updated.
    """
    client = get_user_client(access_token)
    response = (
        client.table("applications")
        .select(
            "id, status, application_date, deadline, application_url, notes, "
            "created_at, updated_at, "
            "programmes("
            "  id, programme_name, degree_level, field, study_mode, duration, "
            "  programme_url, application_url, "
            "  universities(id, name, country, city, website_url)"
            ")"
        )
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return response.data or []


def get_application(user_id: str, access_token: str, application_id: int) -> dict[str, Any] | None:
    """Fetch one application with its programme + university."""
    client = get_user_client(access_token)
    response = (
        client.table("applications")
        .select(
            "id, status, application_date, deadline, application_url, notes, "
            "created_at, updated_at, "
            "programmes("
            "  id, programme_name, degree_level, field, study_mode, duration, "
            "  programme_url, application_url, "
            "  universities(id, name, country, city, website_url)"
            ")"
        )
        .eq("user_id", user_id)
        .eq("id", application_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


def start_application(user_id: str, access_token: str, programme_id: int) -> dict[str, Any]:
    """
    Create an application in 'not_started' status.

    Idempotent — if one already exists for this programme, returns it.
    """
    client = get_user_client(access_token)
    existing = (
        client.table("applications")
        .select("*")
        .eq("user_id", user_id)
        .eq("programme_id", programme_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    response = (
        client.table("applications")
        .insert({
            "user_id": user_id,
            "programme_id": programme_id,
            "status": "not_started",
        })
        .execute()
    )
    return response.data[0]


def update_application(
    user_id: str,
    access_token: str,
    application_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Update application fields. Only whitelisted columns are written.
    """
    allowed = {"status", "application_date", "deadline", "application_url", "notes"}
    clean = {k: v for k, v in payload.items() if k in allowed}

    client = get_user_client(access_token)
    response = (
        client.table("applications")
        .update(clean)
        .eq("user_id", user_id)
        .eq("id", application_id)
        .execute()
    )
    return response.data[0] if response.data else {}


def delete_application(user_id: str, access_token: str, application_id: int) -> None:
    client = get_user_client(access_token)
    client.table("applications").delete().eq("user_id", user_id).eq("id", application_id).execute()


def count_applications(user_id: str, access_token: str) -> int:
    """Total tracked applications."""
    client = get_user_client(access_token)
    response = (
        client.table("applications")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    return response.count or 0


def applications_by_status(user_id: str, access_token: str) -> dict[str, int]:
    """Counts per status, for dashboard widgets."""
    client = get_user_client(access_token)
    response = (
        client.table("applications")
        .select("status")
        .eq("user_id", user_id)
        .execute()
    )
    counts: dict[str, int] = {}
    for row in response.data or []:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return counts


# ============================================================
# Deadline helpers
# ============================================================

def deadline_label(deadline_str: str | None) -> dict[str, Any]:
    """
    Humanise a deadline string.

    Returns a dict:
      { "text": "12 days left", "tone": "warning" | "danger" | "success" | "secondary",
        "days": <int or None> }

    tone is what the UI uses to color the badge.
    """
    if not deadline_str:
        return {"text": "No deadline set", "tone": "secondary", "days": None}

    try:
        d = datetime.strptime(str(deadline_str)[:10], "%Y-%m-%d").date()
    except ValueError:
        return {"text": "Invalid date", "tone": "secondary", "days": None}

    delta = (d - date.today()).days

    if delta < 0:
        return {"text": f"Overdue by {abs(delta)} day{'s' if abs(delta) != 1 else ''}",
                "tone": "danger", "days": delta}
    if delta == 0:
        return {"text": "Due today", "tone": "danger", "days": 0}
    if delta <= 7:
        return {"text": f"{delta} day{'s' if delta != 1 else ''} left",
                "tone": "danger", "days": delta}
    if delta <= 30:
        return {"text": f"{delta} days left", "tone": "warning", "days": delta}
    return {"text": f"{delta} days left", "tone": "success", "days": delta}
"""
Saved programmes service.

All operations go through the USER client — RLS enforces ownership.
"""

from typing import Any

from services.supabase_service import get_user_client


def is_saved(user_id: str, access_token: str, programme_id: int) -> bool:
    """Return True if this programme is already saved by this user."""
    client = get_user_client(access_token)
    response = (
        client.table("saved_programmes")
        .select("id")
        .eq("user_id", user_id)
        .eq("programme_id", programme_id)
        .limit(1)
        .execute()
    )
    return bool(response.data)


def save_programme(user_id: str, access_token: str, programme_id: int) -> None:
    """Save a programme. Silently succeeds if already saved."""
    client = get_user_client(access_token)
    try:
        client.table("saved_programmes").insert({
            "user_id": user_id,
            "programme_id": programme_id,
        }).execute()
    except Exception:
        # Unique constraint violation = already saved. That's fine.
        pass


def unsave_programme(user_id: str, access_token: str, programme_id: int) -> None:
    """Remove a programme from the user's saved list."""
    client = get_user_client(access_token)
    client.table("saved_programmes").delete().eq(
        "user_id", user_id
    ).eq("programme_id", programme_id).execute()


def list_saved_programme_ids(user_id: str, access_token: str) -> set[int]:
    """Return a set of programme ids saved by this user (for bulk UI checks)."""
    client = get_user_client(access_token)
    response = (
        client.table("saved_programmes")
        .select("programme_id")
        .eq("user_id", user_id)
        .execute()
    )
    return {row["programme_id"] for row in (response.data or [])}


def list_saved_programmes(user_id: str, access_token: str) -> list[dict[str, Any]]:
    """
    Return the user's saved programmes with nested university + requirements.
    Used by the saved programmes list page (Phase 12).
    """
    client = get_user_client(access_token)
    response = (
        client.table("saved_programmes")
        .select(
            "created_at, "
            "programmes("
            "  id, programme_name, degree_level, field, specialization, "
            "  language, study_mode, duration, programme_url, application_url, "
            "  universities(id, name, country, city, website_url), "
            "  admission_requirements("
            "    minimum_cgpa, minimum_cgpa_scale, minimum_degree, "
            "    required_field, english_requirement, "
            "    ielts_required, ielts_minimum_score, "
            "    toefl_required, toefl_minimum_score, gre_required, "
            "    work_experience_required, other_requirements, "
            "    source_url, verification_status, last_verified_at"
            "  )"
            ")"
        )
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []
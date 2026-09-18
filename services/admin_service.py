"""
Admin service — CRUD for universities, programmes, and requirements.

Uses the ADMIN (service_role) client, which bypasses RLS.
Every calling route must be protected by @admin_required.
"""

from typing import Any

from services.supabase_service import get_admin_client


# ============================================================
# Universities
# ============================================================

UNIVERSITY_FIELDS = {
    "name", "country", "state_region", "city",
    "website_url", "official_email", "description",
    "source_url", "status",
}


def list_all_universities() -> list[dict[str, Any]]:
    client = get_admin_client()
    response = (
        client.table("universities")
        .select("id, name, country, city, status, created_at, updated_at")
        .order("name")
        .execute()
    )
    return response.data or []


def get_university(university_id: int) -> dict[str, Any] | None:
    client = get_admin_client()
    response = (
        client.table("universities")
        .select("*")
        .eq("id", university_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def create_university(payload: dict[str, Any]) -> dict[str, Any]:
    clean = {k: v for k, v in payload.items() if k in UNIVERSITY_FIELDS}
    client = get_admin_client()
    response = client.table("universities").insert(clean).execute()
    return response.data[0] if response.data else {}


def update_university(university_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    clean = {k: v for k, v in payload.items() if k in UNIVERSITY_FIELDS}
    client = get_admin_client()
    response = (
        client.table("universities")
        .update(clean)
        .eq("id", university_id)
        .execute()
    )
    return response.data[0] if response.data else {}


# ============================================================
# Programmes
# ============================================================

PROGRAMME_FIELDS = {
    "university_id", "programme_name", "degree_level",
    "field", "specialization", "language", "study_mode", "duration",
    "programme_url", "application_url", "status",
}


def list_all_programmes() -> list[dict[str, Any]]:
    client = get_admin_client()
    response = (
        client.table("programmes")
        .select(
            "id, programme_name, degree_level, field, status, created_at, "
            "universities(id, name, country)"
        )
        .order("programme_name")
        .execute()
    )
    return response.data or []


def get_programme(programme_id: int) -> dict[str, Any] | None:
    client = get_admin_client()
    response = (
        client.table("programmes")
        .select("*, universities(id, name, country)")
        .eq("id", programme_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def create_programme(payload: dict[str, Any]) -> dict[str, Any]:
    clean = {k: v for k, v in payload.items() if k in PROGRAMME_FIELDS}
    client = get_admin_client()
    response = client.table("programmes").insert(clean).execute()
    return response.data[0] if response.data else {}


def update_programme(programme_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    clean = {k: v for k, v in payload.items() if k in PROGRAMME_FIELDS}
    client = get_admin_client()
    response = (
        client.table("programmes")
        .update(clean)
        .eq("id", programme_id)
        .execute()
    )
    return response.data[0] if response.data else {}


# ============================================================
# Requirements
# ============================================================

REQUIREMENT_FIELDS = {
    "programme_id", "minimum_cgpa", "minimum_cgpa_scale",
    "minimum_degree", "required_field", "english_requirement",
    "ielts_required", "ielts_minimum_score",
    "toefl_required", "toefl_minimum_score",
    "gre_required", "work_experience_required", "other_requirements",
    "source_url", "verification_status",
}


def get_requirements_for_programme(programme_id: int) -> dict[str, Any] | None:
    client = get_admin_client()
    response = (
        client.table("admission_requirements")
        .select("*")
        .eq("programme_id", programme_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def upsert_requirements(programme_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    payload["programme_id"] = programme_id
    clean = {k: v for k, v in payload.items() if k in REQUIREMENT_FIELDS}
    client = get_admin_client()
    response = (
        client.table("admission_requirements")
        .upsert(clean, on_conflict="programme_id")
        .execute()
    )
    return response.data[0] if response.data else {}


# ============================================================
# Stats
# ============================================================

def stats() -> dict[str, int]:
    client = get_admin_client()
    uni = client.table("universities").select("id", count="exact").execute()
    prog = client.table("programmes").select("id", count="exact").execute()
    req = client.table("admission_requirements").select("id", count="exact").execute()
    return {
        "universities": uni.count or 0,
        "programmes": prog.count or 0,
        "requirements": req.count or 0,
    }
"""
University and programme read service.

Uses the PUBLIC client — universities and programmes are publicly
readable per RLS (Phase 6). No login required to browse.
"""

from typing import Any

from services.supabase_service import get_public_client


def list_universities(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """Return a page of universities with their programme count."""
    client = get_public_client()
    response = (
        client.table("universities")
        .select("id, name, country, city, website_url, status, "
                "programmes(count)")
        .eq("status", "active")
        .order("name")
        .range(offset, offset + limit - 1)
        .execute()
    )
    rows = response.data or []
    # Flatten the nested count: programmes: [{count: N}] -> programme_count: N
    for row in rows:
        progs = row.pop("programmes", []) or []
        row["programme_count"] = progs[0]["count"] if progs else 0
    return rows


def count_universities() -> int:
    """Return total number of active universities."""
    client = get_public_client()
    response = (
        client.table("universities")
        .select("id", count="exact")
        .eq("status", "active")
        .execute()
    )
    return response.count or 0


def get_university(university_id: int) -> dict[str, Any] | None:
    """
    Return one university with all its programmes and their requirements.

    Uses a nested select — Supabase joins across the foreign keys for us.
    """
    client = get_public_client()
    response = (
        client.table("universities")
        .select(
            "id, name, country, state_region, city, website_url, "
            "description, official_email, status, "
            "programmes("
            "  id, programme_name, degree_level, field, specialization, "
            "  language, study_mode, duration, programme_url, "
            "  application_url, status, "
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
        .eq("id", university_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]
def programmes_with_requirements(university_id: int) -> list[dict[str, Any]]:
    """
    Return a flat list of programmes with their requirements attached,
    ready for the matching engine.
    """
    uni = get_university(university_id)
    if uni is None:
        return []
    result = []
    for prog in uni.get("programmes", []) or []:
        reqs = prog.get("admission_requirements") or []
        prog_copy = {k: v for k, v in prog.items() if k != "admission_requirements"}
        prog_copy["requirements"] = reqs[0] if reqs else None
        result.append(prog_copy)
    return result
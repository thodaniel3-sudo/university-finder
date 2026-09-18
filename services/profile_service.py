"""
Student profile service.

All reads and writes go through the USER client — never the admin client.
RLS ensures a user can only touch their own row; this service never has
to enforce that itself.
"""

from typing import Any

from services.supabase_service import get_user_client


PROFILE_FIELDS = [
    "full_name",
    "country",
    "degree_level",
    "desired_programme",
    "desired_field",
    "previous_degree",
    "previous_field",
    "cgpa",
    "cgpa_scale",
    "graduation_year",
    "english_proficiency",
    "ielts_score",
    "toefl_score",
    "other_info",
]


def get_profile(user_id: str, access_token: str) -> dict[str, Any] | None:
    """Return the user's profile row, or None if not created yet."""
    client = get_user_client(access_token)
    response = (
        client.table("student_profiles")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


def upsert_profile(user_id: str, access_token: str, data: dict[str, Any]) -> dict[str, Any]:
    """
    Insert or update the user's profile.

    Only whitelisted fields are accepted — we never let the client set
    arbitrary columns like created_at or user_id.
    """
    payload = {k: v for k, v in data.items() if k in PROFILE_FIELDS}
    payload["user_id"] = user_id

    client = get_user_client(access_token)
    response = (
        client.table("student_profiles")
        .upsert(payload, on_conflict="user_id")
        .execute()
    )
    return response.data[0] if response.data else {}


def profile_completion(profile: dict[str, Any] | None) -> dict[str, Any]:
    """
    Compute how complete the profile is.

    Returns a dict with `percent` (0-100) and `missing` (list of field labels).
    """
    if not profile:
        return {"percent": 0, "missing": ["All fields"]}

    # Fields we consider essential for the matching engine.
    essential = {
        "full_name": "Full name",
        "country": "Country",
        "degree_level": "Degree level",
        "previous_degree": "Previous degree",
        "previous_field": "Previous field of study",
        "cgpa": "CGPA",
        "cgpa_scale": "CGPA scale",
        "graduation_year": "Graduation year",
    }
    # Fields we consider useful but optional.
    optional = {
        "desired_programme": "Desired programme",
        "desired_field": "Desired field",
        "english_proficiency": "English proficiency",
        "ielts_score": "IELTS score",
        "toefl_score": "TOEFL score",
    }

    missing_essential = [label for key, label in essential.items()
                         if not profile.get(key)]
    missing_optional  = [label for key, label in optional.items()
                         if not profile.get(key)]

    # Essential fields count double weight toward completion.
    total_weight = len(essential) * 2 + len(optional)
    earned = (
        (len(essential) - len(missing_essential)) * 2
        + (len(optional) - len(missing_optional))
    )
    percent = round(earned / total_weight * 100) if total_weight else 0

    return {
        "percent": percent,
        "missing": missing_essential,      # only essentials for now
        "missing_optional": missing_optional,
    }
from typing import Any

from services.supabase_service import get_user_client


PROFILE_FIELDS = [
    "full_name",
    "country",
    "degree_level",
    "desired_programme",
    "desired_field",
    "previous_degree",
    "previous_field",
    "cgpa",
    "cgpa_scale",
    "graduation_year",
    "english_proficiency",
    "ielts_score",
    "toefl_score",
    "other_info",
]


def get_profile(user_id: str, access_token: str) -> dict[str, Any] | None:
    """Return the user's profile row, or None if not created yet."""
    client = get_user_client(access_token)
    response = (
        client.table("student_profiles")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


def upsert_profile(user_id: str, access_token: str, data: dict[str, Any]) -> dict[str, Any]:
    """
    Insert or update the user's profile.

    Only whitelisted fields are accepted — we never let the client set
    arbitrary columns like created_at or user_id.
    """
    payload = {k: v for k, v in data.items() if k in PROFILE_FIELDS}
    payload["user_id"] = user_id

    client = get_user_client(access_token)
    response = (
        client.table("student_profiles")
        .upsert(payload, on_conflict="user_id")
        .execute()
    )
    return response.data[0] if response.data else {}


def profile_completion(profile: dict[str, Any] | None) -> dict[str, Any]:
    """
    Compute how complete the profile is.

    Returns a dict with `percent` (0-100) and `missing` (list of field labels).
    """
    if not profile:
        return {"percent": 0, "missing": ["All fields"]}

    # Fields we consider essential for the matching engine.
    essential = {
        "full_name": "Full name",
        "country": "Country",
        "degree_level": "Degree level",
        "previous_degree": "Previous degree",
        "previous_field": "Previous field of study",
        "cgpa": "CGPA",
        "cgpa_scale": "CGPA scale",
        "graduation_year": "Graduation year",
    }
    # Fields we consider useful but optional.
    optional = {
        "desired_programme": "Desired programme",
        "desired_field": "Desired field",
        "english_proficiency": "English proficiency",
        "ielts_score": "IELTS score",
        "toefl_score": "TOEFL score",
    }

    missing_essential = [label for key, label in essential.items()
                         if not profile.get(key)]
    missing_optional = [label for key, label in optional.items()
                        if not profile.get(key)]

    # Essential fields count double weight toward completion.
    total_weight = len(essential) * 2 + len(optional)
    earned = (
        (len(essential) - len(missing_essential)) * 2
        + (len(optional) - len(missing_optional))
    )
    percent = round(earned / total_weight * 100) if total_weight else 0

    return {
        "percent": percent,
        "missing": missing_essential,
        "missing_optional": missing_optional,
    }
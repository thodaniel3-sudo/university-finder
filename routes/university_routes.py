"""
Public university browse and detail routes.
The detail page shows a matching panel if the user is logged in
and has a student profile.
"""

from flask import Blueprint, abort, render_template, request, session

from services.matching_service import STATUS_COLORS, STATUS_LABELS, match_programme
from services.profile_service import get_profile
from services.university_service import (
    count_universities,
    get_university,
    list_countries,
    list_universities,
)

university_bp = Blueprint("universities", __name__)

PAGE_SIZE = 10


def _normalise_requirements(raw):
    """
    Supabase returns `admission_requirements` nested either as a
    one-element list or a single dict depending on query shape.

    Return a single dict or None.
    """
    if isinstance(raw, list):
        return raw[0] if raw else None
    if isinstance(raw, dict):
        return raw
    return None


@university_bp.route("/universities")
def list_view():
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    # Country filter from the query string, sanitized.
    raw_country = (request.args.get("country") or "").strip()
    country = raw_country if raw_country else None

    offset = (page - 1) * PAGE_SIZE
    rows = list_universities(limit=PAGE_SIZE, offset=offset, country=country)
    total = count_universities(country=country)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    countries = list_countries()
    # Grand total across all countries, for the summary line.
    grand_total = sum(c["count"] for c in countries)

    return render_template(
        "universities.html",
        universities=rows,
        page=page,
        total_pages=total_pages,
        total=total,
        country=country,
        countries=countries,
        grand_total=grand_total,
    )


@university_bp.route("/universities/<int:university_id>")
def detail_view(university_id: int):
    uni = get_university(university_id)
    if uni is None:
        abort(404)

    matches = {}
    profile = None
    user_id = session.get("user_id")
    token = session.get("access_token")

    if user_id and token:
        try:
            profile = get_profile(user_id, token)
        except Exception:
            profile = None

        if profile:
            for prog in uni.get("programmes", []) or []:
                req = _normalise_requirements(prog.get("admission_requirements"))
                matches[prog["id"]] = match_programme(profile, prog, req)

    return render_template(
        "university.html",
        university=uni,
        profile=profile,
        matches=matches,
        status_labels=STATUS_LABELS,
        status_colors=STATUS_COLORS,
    )
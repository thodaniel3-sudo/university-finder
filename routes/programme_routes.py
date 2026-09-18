"""
Programme detail page and save/unsave actions.
"""

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.auth_decorators import current_user, login_required
from services.matching_service import (
    STATUS_COLORS,
    STATUS_LABELS,
    MatchStatus,
    match_programme,
)
from services.profile_service import get_profile
from services.saved_service import is_saved, save_programme, unsave_programme
from services.supabase_service import get_public_client

programme_bp = Blueprint("programmes", __name__)


def _normalise_requirements(raw):
    """Accept list or dict shape from Supabase and return one dict or None."""
    if isinstance(raw, list):
        return raw[0] if raw else None
    if isinstance(raw, dict):
        return raw
    return None


def _get_programme_full(programme_id: int) -> dict | None:
    """
    Fetch one programme with its university and admission requirements.
    Uses the PUBLIC client — programme metadata is publicly readable.
    """
    client = get_public_client()
    response = (
        client.table("programmes")
        .select(
            "id, programme_name, degree_level, field, specialization, "
            "language, study_mode, duration, programme_url, application_url, "
            "status, "
            "universities(id, name, country, state_region, city, website_url, official_email), "
            "admission_requirements("
            "  minimum_cgpa, minimum_cgpa_scale, minimum_degree, "
            "  required_field, english_requirement, "
            "  ielts_required, ielts_minimum_score, "
            "  toefl_required, toefl_minimum_score, gre_required, "
            "  work_experience_required, other_requirements, "
            "  source_url, verification_status, last_verified_at"
            ")"
        )
        .eq("id", programme_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


def _group_matches(match) -> dict[str, list]:
    """
    Group RequirementMatch results by status for the template.

    Returns a dict of lists keyed by status name.
    """
    grouped = {
        MatchStatus.MEETS.value: [],
        MatchStatus.DOES_NOT_MEET.value: [],
        MatchStatus.UNKNOWN.value: [],
        MatchStatus.REQUIRES_VERIFICATION.value: [],
    }
    for r in match.requirements:
        grouped[r.status.value].append(r)
    return grouped


@programme_bp.route("/programmes/<int:programme_id>")
def detail_view(programme_id: int):
    prog = _get_programme_full(programme_id)
    if prog is None:
        abort(404)

    req = _normalise_requirements(prog.get("admission_requirements"))

    # Optional matching
    match = None
    grouped = None
    saved = False
    user_id = session.get("user_id")
    token = session.get("access_token")

    if user_id and token:
        try:
            profile = get_profile(user_id, token)
        except Exception:
            profile = None

        if profile:
            match = match_programme(profile, prog, req)
            grouped = _group_matches(match)

        try:
            saved = is_saved(user_id, token, programme_id)
        except Exception:
            saved = False

    return render_template(
        "programme.html",
        programme=prog,
        university=prog.get("universities") or {},
        requirements=req,
        match=match,
        grouped=grouped,
        saved=saved,
        status_labels=STATUS_LABELS,
        status_colors=STATUS_COLORS,
    )


@programme_bp.route("/programmes/<int:programme_id>/save", methods=["POST"])
@login_required
def save_view(programme_id: int):
    user = current_user()
    try:
        save_programme(user["id"], user["access_token"], programme_id)
        flash("Programme saved.", "success")
    except Exception:
        flash("Could not save the programme. Please try again.", "danger")

    if request.headers.get("Accept") == "application/json":
        return jsonify({"saved": True})
    return redirect(url_for("programmes.detail_view", programme_id=programme_id))


@programme_bp.route("/programmes/<int:programme_id>/unsave", methods=["POST"])
@login_required
def unsave_view(programme_id: int):
    user = current_user()
    try:
        unsave_programme(user["id"], user["access_token"], programme_id)
        flash("Removed from saved programmes.", "info")
    except Exception:
        flash("Could not remove the programme. Please try again.", "danger")

    if request.headers.get("Accept") == "application/json":
        return jsonify({"saved": False})
    return redirect(url_for("programmes.detail_view", programme_id=programme_id))
"""
Saved programmes list page.

Reads the user's DB-saved programmes and their web-saved external
programmes, and renders them in two sections on /saved.
"""

from flask import Blueprint, render_template
from services.saved_service import list_all_saved_for_emailing
from services.auth_decorators import current_user, login_required
from services.external_service import list_external
from services.matching_service import STATUS_COLORS, STATUS_LABELS, match_programme
from services.profile_service import get_profile
from services.saved_service import list_saved_programmes

saved_bp = Blueprint("saved", __name__)


def _normalise_requirements(raw):
    """Accept list or dict shape from Supabase; return one dict or None."""
    if isinstance(raw, list):
        return raw[0] if raw else None
    if isinstance(raw, dict):
        return raw
    return None


def _normalise_university(raw):
    """Supabase returns the nested university as list or dict."""
    if isinstance(raw, list):
        return raw[0] if raw else {}
    if isinstance(raw, dict):
        return raw
    return {}


@saved_bp.route("/saved")
@login_required
def list_view():
    user = current_user()
    rows = list_saved_programmes(user["id"], user["access_token"]) or []

    # Load profile once — used for optional match computations.
    profile = None
    try:
        profile = get_profile(user["id"], user["access_token"])
    except Exception:
        profile = None

    db_items = []
    for row in rows:
        prog = row.get("programmes") or {}
        if isinstance(prog, list):
            prog = prog[0] if prog else {}
        if not prog:
            continue

        uni = _normalise_university(prog.get("universities"))
        req = _normalise_requirements(prog.get("admission_requirements"))

        match = None
        if profile:
            match = match_programme(profile, prog, req)

        db_items.append({
            "saved_at": row.get("created_at"),
            "programme": prog,
            "university": uni,
            "requirements": req,
            "match": match,
        })

    # Fetch external (web-saved) programmes.
    try:
        external_items = list_external(user["id"], user["access_token"])
    except Exception:
        external_items = []

    return render_template(
        "saved.html",
        db_items=db_items,
        external_items=external_items,
        status_labels=STATUS_LABELS,
        status_colors=STATUS_COLORS,
    )

@saved_bp.route("/saved/programs")
@login_required
def programs_view():
    """
    Dedicated page for the 'email all saved programmes' workflow.

    Shows every saved programme (DB + web) in one list, sorted so
    not-yet-emailed items appear first.
    """
    user = current_user()
    try:
        result = list_all_saved_for_emailing(user["id"], user["access_token"])
    except Exception:
        result = {
            "items": [],
            "total": 0,
            "db_count": 0,
            "external_count": 0,
            "not_emailed_count": 0,
        }
    return render_template("saved_programs.html", result=result)
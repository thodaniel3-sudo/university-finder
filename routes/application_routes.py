"""
Application tracker routes.
"""

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from services.application_service import (
    deadline_label,
    delete_application,
    get_application,
    list_applications,
    start_application,
    update_application,
)
from services.application_statuses import STATUS_COLORS, STATUS_LABELS
from services.auth_decorators import current_user, login_required
from services.forms import ApplicationForm

application_bp = Blueprint("applications", __name__)


def _normalise_nested(raw):
    """Supabase returns one-to-one relations as list or dict."""
    if isinstance(raw, list):
        return raw[0] if raw else {}
    if isinstance(raw, dict):
        return raw
    return {}


def _normalise_row(row: dict) -> dict:
    """Flatten a raw application row for template use."""
    prog = _normalise_nested(row.get("programmes"))
    uni = _normalise_nested(prog.get("universities")) if prog else {}

    return {
        "id": row.get("id"),
        "status": row.get("status"),
        "status_label": STATUS_LABELS.get(row.get("status"), "Unknown"),
        "status_color": STATUS_COLORS.get(row.get("status"), "secondary"),
        "application_date": row.get("application_date"),
        "deadline": row.get("deadline"),
        "deadline_info": deadline_label(row.get("deadline")),
        "application_url": row.get("application_url"),
        "notes": row.get("notes"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "programme": prog,
        "university": uni,
    }


@application_bp.route("/applications")
@login_required
def list_view():
    user = current_user()
    rows = list_applications(user["id"], user["access_token"]) or []
    items = [_normalise_row(r) for r in rows]

    # Group counts by status for a summary bar at the top.
    status_summary: dict[str, int] = {}
    for item in items:
        status_summary[item["status"]] = status_summary.get(item["status"], 0) + 1

    return render_template(
        "applications.html",
        applications=items,
        status_summary=status_summary,
        status_labels=STATUS_LABELS,
        status_colors=STATUS_COLORS,
    )


@application_bp.route("/applications/<int:application_id>", methods=["GET", "POST"])
@login_required
def detail_view(application_id: int):
    user = current_user()
    raw = get_application(user["id"], user["access_token"], application_id)
    if raw is None:
        abort(404)

    item = _normalise_row(raw)
    form = ApplicationForm()

    if form.validate_on_submit():
        payload = {
            "status": form.status.data,
            "application_date": (
                form.application_date.data.isoformat()
                if form.application_date.data else None
            ),
            "deadline": (
                form.deadline.data.isoformat()
                if form.deadline.data else None
            ),
            "application_url": form.application_url.data or None,
            "notes": form.notes.data or None,
        }
        update_application(user["id"], user["access_token"], application_id, payload)
        flash("Application updated.", "success")
        return redirect(url_for("applications.detail_view", application_id=application_id))

    # On GET, pre-fill form.
    if not form.is_submitted():
        form.status.data = item["status"]
        if item["application_date"]:
            try:
                from datetime import datetime
                form.application_date.data = datetime.strptime(
                    str(item["application_date"])[:10], "%Y-%m-%d"
                ).date()
            except ValueError:
                pass
        if item["deadline"]:
            try:
                from datetime import datetime
                form.deadline.data = datetime.strptime(
                    str(item["deadline"])[:10], "%Y-%m-%d"
                ).date()
            except ValueError:
                pass
        form.application_url.data = item["application_url"]
        form.notes.data = item["notes"]

    return render_template(
        "application.html",
        application=item,
        form=form,
        status_labels=STATUS_LABELS,
        status_colors=STATUS_COLORS,
    )


@application_bp.route("/applications/start/<int:programme_id>", methods=["POST"])
@login_required
def start_view(programme_id: int):
    user = current_user()
    try:
        app_row = start_application(user["id"], user["access_token"], programme_id)
        flash("Application started.", "success")
        return redirect(url_for("applications.detail_view", application_id=app_row["id"]))
    except Exception as exc:
        flash(f"Could not start application: {exc}", "danger")
        return redirect(url_for("programmes.detail_view", programme_id=programme_id))


@application_bp.route("/applications/<int:application_id>/delete", methods=["POST"])
@login_required
def delete_view(application_id: int):
    user = current_user()
    delete_application(user["id"], user["access_token"], application_id)
    flash("Application deleted.", "info")
    return redirect(url_for("applications.list_view"))
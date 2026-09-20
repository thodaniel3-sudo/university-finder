"""
Routes for saved external (web-discovered) programmes.

This is a parallel, lighter-weight tracking flow to /saved and
/applications — for programmes the user found via web search but
that aren't in our curated database.
"""

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.application_statuses import STATUS_COLORS, STATUS_LABELS
from services.auth_decorators import current_user, login_required
from services.external_service import (
    delete_external,
    get_external,
    list_external,
    save_external,
    update_external,
)
from services.forms import ExternalProgrammeForm

external_bp = Blueprint("external", __name__, url_prefix="/external")


@external_bp.route("/save", methods=["POST"])
@login_required
def save_view():
    """Called from search results page. Form fields carry the result data."""
    user = current_user()

    title = (request.form.get("title") or "").strip()
    url = (request.form.get("url") or "").strip()
    source_domain = (request.form.get("source_domain") or "").strip()
    description = (request.form.get("description") or "").strip()
    search_query = (request.form.get("search_query") or "").strip()

    if not url or not title:
        flash("Missing title or URL — could not save.", "danger")
        return redirect(url_for("search.search_view", q=search_query))

    try:
        row = save_external(
            user["id"], user["access_token"],
            title=title, url=url, source_domain=source_domain,
            description=description, search_query=search_query,
        )
        flash("Saved to your external programmes list.", "success")
        return redirect(url_for("external.detail_view", external_id=row["id"]))
    except Exception as exc:
        flash(f"Could not save: {exc}", "danger")
        return redirect(url_for("search.search_view", q=search_query))


@external_bp.route("/<int:external_id>", methods=["GET", "POST"])
@login_required
def detail_view(external_id: int):
    user = current_user()
    row = get_external(user["id"], user["access_token"], external_id)
    if row is None:
        abort(404)

    form = ExternalProgrammeForm(data=row)

    if form.validate_on_submit():
        try:
            update_external(user["id"], user["access_token"], external_id, {
                "status": form.status.data,
                "notes": form.notes.data or None,
            })
            flash("Saved.", "success")
            return redirect(url_for("external.detail_view", external_id=external_id))
        except Exception as exc:
            flash(f"Could not save: {exc}", "danger")

    return render_template(
        "external_detail.html",
        external=row,
        form=form,
        status_labels=STATUS_LABELS,
        status_colors=STATUS_COLORS,
    )


@external_bp.route("/<int:external_id>/delete", methods=["POST"])
@login_required
def delete_view(external_id: int):
    user = current_user()
    delete_external(user["id"], user["access_token"], external_id)
    flash("Removed from external programmes.", "info")
    return redirect(url_for("saved.list_view"))


@external_bp.route("/<int:external_id>/compose", methods=["GET", "POST"])
@login_required
def compose_view(external_id: int):
    """
    Lightweight email composition for a web-discovered programme.

    Unlike /emails/compose, this doesn't use the university/programme
    dropdowns because we don't have a DB record. Instead, the user
    pastes the recipient email and confirms the subject/body.
    """
    user = current_user()
    row = get_external(user["id"], user["access_token"], external_id)
    if row is None:
        abort(404)

    # If the form was submitted, hand off to the existing review flow.
    if request.method == "POST":
        recipient = (request.form.get("recipient_email") or "").strip()
        subject = (request.form.get("subject") or "").strip()
        body = (request.form.get("body") or "").strip()

        if not recipient or not subject or not body:
            flash("All fields are required.", "danger")
        else:
            # Stash in session for /emails/review to pick up.
            session["email_draft"] = {
                "recipient_email": recipient,
                "subject": subject,
                "body": body,
                "email_type": "general_inquiry",
                "university_id": None,
                "programme_id": None,
                "external_programme_id": external_id,
            }
            return redirect(url_for("emails.review_view"))

    # On GET, generate a polite draft using the external record.
    from services.external_email_generator import generate_external_draft

    profile = None
    try:
        from services.profile_service import get_profile
        profile = get_profile(user["id"], user["access_token"])
    except Exception:
        pass

    draft = generate_external_draft(profile=profile, external=row)

    return render_template(
        "external_compose.html",
        external=row,
        draft=draft,
    )
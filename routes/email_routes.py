"""
Email generation and handoff flow.
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

from services.auth_decorators import current_user, login_required
from services.email_generator import generate_email_draft
from services.email_handoff import (
    build_gmail_compose_url,
    build_mailto_url,
    is_mailto_safe,
)
from services.email_purposes import PURPOSE_LABELS
from services.email_service import (
    create_draft,
    delete_email,
    get_email,
    list_emails,
    mark_failed,
    mark_handed_off,
    mark_sent,
)
from services.forms import EmailComposeForm, EmailReviewForm
from services.profile_service import get_profile
from services.supabase_service import get_public_client

email_bp = Blueprint("emails", __name__)


def _normalise_nested(raw):
    """Supabase returns one-to-one nested selects as list or dict."""
    if isinstance(raw, list):
        return raw[0] if raw else None
    if isinstance(raw, dict):
        return raw
    return None


@email_bp.route("/emails")
@login_required
def list_view():
    user = current_user()
    try:
        rows = list_emails(user["id"], user["access_token"])
    except Exception:
        rows = []

    items = []
    for row in rows:
        uni = _normalise_nested(row.get("universities")) or {}
        prog = _normalise_nested(row.get("programmes")) or {}
        items.append({
            "id": row.get("id"),
            "status": row.get("status"),
            "email_type": row.get("email_type"),
            "email_type_label": PURPOSE_LABELS.get(row.get("email_type"), "—"),
            "recipient_email": row.get("recipient_email"),
            "subject": row.get("subject"),
            "sent_at": row.get("sent_at"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "error_message": row.get("error_message"),
            "university": uni,
            "programme": prog,
        })

    return render_template(
        "emails.html",
        emails=items,
        purpose_labels=PURPOSE_LABELS,
    )


@email_bp.route("/emails/compose", methods=["GET", "POST"])
@login_required
def compose_view():
    user = current_user()
    form = EmailComposeForm()

    client = get_public_client()

    # Load dropdown options
    uni_resp = (
        client.table("universities")
        .select("id, name, country")
        .eq("status", "active")
        .order("name")
        .execute()
    )
    universities = uni_resp.data or []

    prog_resp = (
        client.table("programmes")
        .select("id, university_id, programme_name, degree_level")
        .eq("status", "active")
        .order("programme_name")
        .execute()
    )
    programmes = prog_resp.data or []

    # Populate choices at runtime.
    form.university_id.choices = [(0, "-- select --")] + [
        (u["id"], f"{u['name']} ({u.get('country', '')})") for u in universities
    ]
    form.programme_id.choices = [(0, "-- none --")] + [
        (p["id"], f"{p['programme_name']} — {p.get('degree_level', '')}") for p in programmes
    ]

    # ---- Pre-select from query params (used by /saved/programs Send button) ----
    if request.method == "GET":
        preload_prog = request.args.get("programme_id", type=int)
        if preload_prog:
            form.programme_id.data = preload_prog
            # Also pre-select the university
            for p in programmes:
                if p["id"] == preload_prog:
                    form.university_id.data = p["university_id"]
                    break

    if form.validate_on_submit():
        university_id = form.university_id.data or 0
        programme_id = form.programme_id.data or 0

        if not university_id:
            flash("Please select a university.", "danger")
            return render_template("email_compose.html", form=form)

        # Load university
        uni_resp = (
            client.table("universities")
            .select("*")
            .eq("id", university_id)
            .limit(1)
            .execute()
        )
        if not uni_resp.data:
            flash("University not found.", "danger")
            return render_template("email_compose.html", form=form)
        university = uni_resp.data[0]

        # Load programme (optional)
        programme = None
        if programme_id:
            prog_resp = (
                client.table("programmes")
                .select("*")
                .eq("id", programme_id)
                .limit(1)
                .execute()
            )
            if prog_resp.data:
                programme = prog_resp.data[0]

        # Require a profile
        profile = get_profile(user["id"], user["access_token"])
        if not profile:
            flash(
                "Please complete your profile first so we can generate a "
                "personalised draft.",
                "warning",
            )
            return redirect(url_for("profile.view_profile"))

        # Generate draft
        draft = generate_email_draft(
            profile=profile,
            university=university,
            programme=programme,
            purpose=form.email_type.data,
        )

        recipient = (
            university.get("official_email")
            or "admissions@example.com"
        )

        session["email_draft"] = {
            "recipient_email": recipient,
            "subject": draft["subject"],
            "body": draft["body"],
            "email_type": form.email_type.data,
            "university_id": university["id"],
            "programme_id": programme["id"] if programme else None,
            "external_programme_id": None,
        }
        return redirect(url_for("emails.review_view"))

    return render_template("email_compose.html", form=form)


@email_bp.route("/emails/review", methods=["GET", "POST"])
@login_required
def review_view():
    draft = session.get("email_draft")
    if not draft:
        flash("No draft to review. Start a new email.", "warning")
        return redirect(url_for("emails.compose_view"))

    user = current_user()
    form = EmailReviewForm()

    if form.validate_on_submit():
        try:
            row = create_draft(
                user_id=user["id"],
                access_token=user["access_token"],
                recipient_email=form.recipient_email.data,
                reply_to=user["email"],
                subject=form.subject.data,
                body=form.body.data,
                email_type=form.email_type.data,
                university_id=draft.get("university_id"),
                programme_id=draft.get("programme_id"),
                external_programme_id=draft.get("external_programme_id"),
            )
        except Exception as exc:
            flash(f"Could not save draft: {exc}", "danger")
            return render_template("email_review.html", form=form)

        session.pop("email_draft", None)

        flash("Draft saved.", "success")
        return redirect(url_for("emails.detail_view", email_id=row["id"]))

    if not form.is_submitted():
        form.recipient_email.data = draft.get("recipient_email", "")
        form.subject.data = draft.get("subject", "")
        form.body.data = draft.get("body", "")
        form.email_type.data = draft.get("email_type", "general_inquiry")

    return render_template("email_review.html", form=form)


@email_bp.route("/emails/<int:email_id>")
@login_required
def detail_view(email_id: int):
    user = current_user()
    row = get_email(user["id"], user["access_token"], email_id)
    if row is None:
        abort(404)

    return render_template(
        "email.html",
        email=row,
        university=_normalise_nested(row.get("universities")) or {},
        programme=_normalise_nested(row.get("programmes")) or {},
        purpose_labels=PURPOSE_LABELS,
    )


@email_bp.route("/emails/<int:email_id>/delete", methods=["POST"])
@login_required
def delete_view(email_id: int):
    user = current_user()
    delete_email(user["id"], user["access_token"], email_id)
    flash("Draft deleted.", "info")
    return redirect(url_for("emails.list_view"))


@email_bp.route("/emails/<int:email_id>/send")
@login_required
def send_view(email_id: int):
    """
    The handoff page. Shows the full message and lets the user choose
    how to send it (mail client, Gmail web, or copy to clipboard).
    """
    user = current_user()
    row = get_email(user["id"], user["access_token"], email_id)
    if row is None:
        abort(404)

    recipient = row.get("recipient_email") or ""
    subject = row.get("subject") or ""
    body = row.get("body") or ""

    mailto_url = build_mailto_url(recipient, subject, body)
    gmail_url = build_gmail_compose_url(recipient, subject, body)

    return render_template(
        "email_send.html",
        email=row,
        university=_normalise_nested(row.get("universities")) or {},
        programme=_normalise_nested(row.get("programmes")) or {},
        purpose_labels=PURPOSE_LABELS,
        mailto_url=mailto_url,
        gmail_url=gmail_url,
        mailto_will_work=is_mailto_safe(mailto_url),
    )


@email_bp.route("/emails/<int:email_id>/mark-handed-off", methods=["POST"])
@login_required
def mark_handed_off_view(email_id: int):
    """Called when the user clicks one of the handoff buttons."""
    user = current_user()
    mark_handed_off(user["id"], user["access_token"], email_id)
    flash(
        "Your email app should open with the message ready. "
        "Come back here once you've sent it.",
        "info",
    )
    return redirect(url_for("emails.detail_view", email_id=email_id))


@email_bp.route("/emails/<int:email_id>/mark-sent", methods=["POST"])
@login_required
def mark_sent_view(email_id: int):
    """User confirmed they sent the email."""
    user = current_user()
    mark_sent(user["id"], user["access_token"], email_id)
    flash("Marked as sent.", "success")
    return redirect(url_for("emails.detail_view", email_id=email_id))


@email_bp.route("/emails/<int:email_id>/mark-failed", methods=["POST"])
@login_required
def mark_failed_view(email_id: int):
    """User reported the email did NOT send."""
    user = current_user()
    mark_failed(user["id"], user["access_token"], email_id)
    flash("Marked as not sent. You can edit and try again.", "warning")
    return redirect(url_for("emails.detail_view", email_id=email_id))
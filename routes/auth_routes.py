"""
Authentication routes: register, login, logout, dashboard.
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.application_service import count_applications
from services.auth_decorators import current_user, login_required
from services.auth_service import AuthError, authenticate_user, register_user
from services.document_service import list_documents
from services.email_service import list_emails
from services.forms import LoginForm, RegisterForm
from services.profile_service import get_profile, profile_completion
from services.saved_service import list_saved_programme_ids
from services.session_refresh import handle_jwt_expired

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("auth.dashboard"))

    form = RegisterForm()

    if form.validate_on_submit():
        try:
            user = register_user(form.email.data.strip().lower(),
                                 form.password.data)
        except AuthError as exc:
            flash(str(exc), "danger")
            return render_template("register.html", form=form)

        flash(
            "Account created. Check your email to confirm your address, "
            "then log in.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("auth.dashboard"))

    form = LoginForm()

    if form.validate_on_submit():
        try:
            user = authenticate_user(form.email.data.strip().lower(),
                                     form.password.data)
        except AuthError as exc:
            flash(str(exc), "danger")
            return render_template("login.html", form=form)

        # Store the access and refresh tokens for authenticated calls.
        session.clear()
        session["user_id"] = user["id"]
        session["user_email"] = user["email"]
        session["access_token"] = user["access_token"]
        session["refresh_token"] = user.get("refresh_token")
        session.permanent = bool(form.remember_me.data)

        # Fetch is_admin from the user's profile and store in session.
        # If the profile doesn't exist yet, treat as non-admin.
        try:
            profile = get_profile(user["id"], user["access_token"])
            session["is_admin"] = bool(profile.get("is_admin")) if profile else False
        except Exception:
            session["is_admin"] = False

        flash("Welcome back.", "success")

        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("auth.dashboard"))

    return render_template("login.html", form=form)


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@auth_bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user()

    try:
        profile = get_profile(user["id"], user["access_token"])
    except Exception as exc:
        if handle_jwt_expired(exc):
            user = current_user()
            profile = get_profile(user["id"], user["access_token"])
        else:
            flash("Your session expired. Please log in again.", "warning")
            return redirect(url_for("auth.login"))

    completion = profile_completion(profile)

    try:
        saved_ids = list_saved_programme_ids(user["id"], user["access_token"])
        saved_count = len(saved_ids)
    except Exception:
        saved_count = 0

    try:
        applications_count = count_applications(user["id"], user["access_token"])
    except Exception:
        applications_count = 0

    try:
        docs = list_documents(user["id"], user["access_token"])
        documents_count = len(docs)
    except Exception:
        documents_count = 0

    try:
        emails = list_emails(user["id"], user["access_token"])
        emails_count = len(emails)
    except Exception:
        emails_count = 0

    return render_template(
        "dashboard.html",
        user=user,
        completion=completion,
        saved_count=saved_count,
        applications_count=applications_count,
        documents_count=documents_count,
        emails_count=emails_count,
    )
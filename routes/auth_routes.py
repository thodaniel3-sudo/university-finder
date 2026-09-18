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
from services.forms import LoginForm, RegisterForm
from services.profile_service import get_profile, profile_completion
from services.saved_service import list_saved_programme_ids
from services.session_refresh import handle_jwt_expired

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # If already logged in, skip straight to dashboard.
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

        # Store the access token for immediate use, and the refresh
        # token so we can silently refresh when the access token expires.
        session.clear()
        session["user_id"] = user["id"]
        session["user_email"] = user["email"]
        session["access_token"] = user["access_token"]
        session["refresh_token"] = user.get("refresh_token")
        session.permanent = bool(form.remember_me.data)

        flash("Welcome back.", "success")

        # Support "next" redirect after login.
        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("auth.dashboard"))

    return render_template("login.html", form=form)


@auth_bp.route("/logout")
def logout():
    # Clear the Flask session. We don't call Supabase sign_out here
    # because we don't store a persistent Supabase session object;
    # Supabase will expire the tokens server-side eventually.
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@auth_bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user()

    # The profile fetch is the first Supabase call. If the access token
    # has expired, we try to refresh it and retry once. If refresh
    # fails, we force the user back to login.
    try:
        profile = get_profile(user["id"], user["access_token"])
    except Exception as exc:
        if handle_jwt_expired(exc):
            # Token refreshed — reload user from session and retry.
            user = current_user()
            profile = get_profile(user["id"], user["access_token"])
        else:
            flash("Your session expired. Please log in again.", "warning")
            return redirect(url_for("auth.login"))

    completion = profile_completion(profile)

    # Saved count — falls back to 0 if Supabase is unreachable.
    try:
        saved_ids = list_saved_programme_ids(user["id"], user["access_token"])
        saved_count = len(saved_ids)
    except Exception:
        saved_count = 0

    # Applications count — same fallback pattern.
    try:
        apps_count = count_applications(user["id"], user["access_token"])
        applications_count = apps_count
    except Exception:
        applications_count = 0

    # Documents count — same fallback pattern.
    try:
        docs = list_documents(user["id"], user["access_token"])
        documents_count = len(docs)
    except Exception:
        documents_count = 0

    return render_template(
        "dashboard.html",
        user=user,
        completion=completion,
        saved_count=saved_count,
        applications_count=applications_count,
        documents_count=documents_count,
    )
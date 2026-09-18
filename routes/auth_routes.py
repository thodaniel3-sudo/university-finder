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

from services.auth_decorators import current_user, login_required
from services.auth_service import AuthError, authenticate_user, register_user
from services.forms import LoginForm, RegisterForm
from services.profile_service import get_profile, profile_completion
from services.saved_service import list_saved_programme_ids

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

        # Store only what we need. Never store the refresh token
        # in the session unless we're prepared to use it safely.
        session.clear()
        session["user_id"] = user["id"]
        session["user_email"] = user["email"]
        session["access_token"] = user["access_token"]
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
    # Clear our Flask session. We don't call Supabase sign_out here
    # because we didn't store the refresh token; Supabase will
    # expire the session server-side eventually.
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@auth_bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    profile = get_profile(user["id"], user["access_token"])
    completion = profile_completion(profile)

    # Count saved programmes so the dashboard can show it.
    # Wrap in try/except so a transient Supabase error doesn't
    # break the whole dashboard — the count just falls back to 0.
    try:
        saved_ids = list_saved_programme_ids(user["id"], user["access_token"])
        saved_count = len(saved_ids)
    except Exception:
        saved_count = 0

    return render_template(
        "dashboard.html",
        user=user,
        completion=completion,
        saved_count=saved_count,
    )
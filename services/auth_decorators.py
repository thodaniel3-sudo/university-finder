"""
Reusable auth decorators for Flask routes.
"""

from functools import wraps

from flask import flash, redirect, session, url_for


def login_required(view_func):
    """
    Redirect to the login page if the user has no session.

    Usage:
        @app.route("/dashboard")
        @login_required
        def dashboard():
            ...
    """
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


def current_user():
    """
    Return the current user dict from the Flask session, or None.

    Only returns what we explicitly stored at login time.
    Never returns secrets, tokens, or passwords.
    """
    uid = session.get("user_id")
    if not uid:
        return None
    return {
        "id": uid,
        "email": session.get("user_email"),
        "access_token": session.get("access_token"),
    }
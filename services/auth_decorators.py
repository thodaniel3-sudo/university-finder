"""
Reusable auth decorators for Flask routes.
"""

from functools import wraps

from flask import flash, redirect, session, url_for


def login_required(view_func):
    """
    Redirect to the login page if the user has no session.
    """
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)
    return wrapped


def current_user():
    """
    Return the current user dict from the Flask session, or None.

    Includes `is_admin` so templates can conditionally show admin links.
    The authoritative admin check still happens server-side in
    services.admin_decorators.admin_required — this is only for UI.
    """
    uid = session.get("user_id")
    if not uid:
        return None
    return {
        "id": uid,
        "email": session.get("user_email"),
        "access_token": session.get("access_token"),
        "is_admin": session.get("is_admin", False),
    }
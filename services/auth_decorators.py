"""
Reusable auth decorators for Flask routes.
"""

import time
from functools import wraps

from flask import flash, redirect, session, url_for

from services.session_refresh import refresh_access_token

# Refresh the token when it has less than this many seconds left.
_REFRESH_WINDOW_SECONDS = 300


def _refresh_if_expiring() -> None:
    """
    Refresh the Supabase access token if it is expired or close to expiry.

    Uses the `expires_at` timestamp stored at login. Falls back to a
    blind refresh if `expires_at` is missing (older sessions).
    """
    if not session.get("user_id"):
        return

    if not session.get("refresh_token"):
        # Session predates refresh-token storage. Force re-login.
        return

    expires_at = session.get("expires_at")
    now = int(time.time())

    if expires_at and (expires_at - now) > _REFRESH_WINDOW_SECONDS:
        return  # token still healthy

    # Expired or close to it — let session_refresh handle the work.
    refresh_access_token()


def login_required(view_func):
    """
    Redirect to login if not authenticated.

    Before running the view, silently refreshes the Supabase access
    token if it is expired or close to expiry.
    """
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))

        _refresh_if_expiring()

        # If refresh failed, session_refresh cleared the session.
        if not session.get("user_id"):
            flash("Your session expired. Please log in again.", "warning")
            return redirect(url_for("auth.login"))

        return view_func(*args, **kwargs)
    return wrapped


def current_user():
    """
    Return the current user dict from the Flask session, or None.

    Refreshes the token first if it is expired or close to expiry,
    so callers always receive a valid access_token.
    """
    uid = session.get("user_id")
    if not uid:
        return None

    _refresh_if_expiring()

    if not session.get("user_id"):
        return None

    return {
        "id": uid,
        "email": session.get("user_email"),
        "access_token": session.get("access_token"),
        "is_admin": session.get("is_admin", False),
    }
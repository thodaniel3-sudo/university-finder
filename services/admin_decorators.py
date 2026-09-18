"""
Admin authorization decorator.

Usage:

    from services.admin_decorators import admin_required

    @admin_bp.route("/admin/universities")
    @admin_required
    def manage_universities():
        ...

The decorator:
  1. Redirects to /login if the user isn't authenticated.
  2. Returns 403 Forbidden if authenticated but not an admin.

Reads is_admin from student_profiles on every request (no caching),
so revoking admin access takes effect immediately.
"""

from functools import wraps

from flask import abort, flash, redirect, session, url_for

from services.profile_service import get_profile
from services.session_refresh import handle_jwt_expired


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        token = session.get("access_token")
        if not user_id or not token:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))

        try:
            profile = get_profile(user_id, token)
        except Exception as exc:
            if handle_jwt_expired(exc):
                token = session.get("access_token")
                user_id = session.get("user_id")
                try:
                    profile = get_profile(user_id, token)
                except Exception:
                    abort(403)
            else:
                abort(403)

        if not profile or not profile.get("is_admin"):
            abort(403)

        return view_func(*args, **kwargs)

    return wrapped
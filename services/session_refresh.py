"""
Session token refresh.

Supabase access tokens expire after about an hour. When that happens,
any Supabase call raises APIError with code 'PGRST303'. This module
catches that situation, uses the stored refresh token to get a new
access token, and lets the caller retry.

Usage in a route or service:

    from services.session_refresh import handle_jwt_expired

    try:
        profile = get_profile(user["id"], user["access_token"])
    except Exception as exc:
        if handle_jwt_expired(exc):
            user = current_user()
            profile = get_profile(user["id"], user["access_token"])
        else:
            # Not recoverable
            return redirect(url_for("auth.login"))
"""

from flask import current_app, session
from supabase import create_client


def is_jwt_expired_error(exc: Exception) -> bool:
    """
    Return True if the exception looks like Supabase's JWT-expired error.

    The SDK raises APIError with a dict payload containing
    {'code': 'PGRST303', 'message': 'JWT expired'}.
    """
    try:
        # postgrest.exceptions.APIError exposes .args[0] as the dict.
        arg = exc.args[0] if exc.args else None
        if isinstance(arg, dict):
            if arg.get("code") == "PGRST303":
                return True
            if arg.get("message") == "JWT expired":
                return True
    except Exception:
        pass
    # Fallback to string matching if we can't introspect.
    return "JWT expired" in str(exc)


def refresh_access_token() -> bool:
    """
    Use the stored refresh token to obtain a new access token.

    Updates session["access_token"] and (usually) session["refresh_token"]
    on success. Returns True on success, False if refresh is impossible.

    Called by routes/services that catch JWT-expired errors.
    """
    refresh_token = session.get("refresh_token")
    if not refresh_token:
        return False

    cfg = current_app.config
    try:
        client = create_client(cfg["SUPABASE_URL"], cfg["SUPABASE_ANON_KEY"])
        response = client.auth.refresh_session(refresh_token)
    except Exception:
        # Refresh failed — token revoked, network error, etc.
        session.clear()
        return False

    if not response or not response.session:
        session.clear()
        return False
    

    session["access_token"] = response.session.access_token
    # Supabase rotates refresh tokens — always store the latest.
    session["refresh_token"] = response.session.refresh_token
    # Store the new expiry so we don't refresh again until we need to.
    expires_at = getattr(response.session, "expires_at", None)
    if expires_at:
        session["expires_at"] = int(expires_at)
    return True


def handle_jwt_expired(exc: Exception) -> bool:
    """
    Convenience: if `exc` is a JWT-expired error, try to refresh.

    Returns True if the error was handled (refresh succeeded),
    False if the caller should treat it as an unrecoverable failure.
    """
    if not is_jwt_expired_error(exc):
        return False
    return refresh_access_token()
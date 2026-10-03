"""
Facebook OAuth routes.

Endpoints:
  GET  /facebook/connect   — redirect the user to Facebook's OAuth dialog
  GET  /facebook/callback  — receive the OAuth code, exchange for tokens,
                             store Page tokens in the Flask session
  GET  /facebook/status    — JSON: whether the user is connected
  POST /facebook/disconnect — clear stored tokens from the session

Tokens are stored in the Flask server-side session (signed cookie),
never in localStorage or exposed to the frontend JavaScript.

Security notes:
  - META_APP_SECRET never leaves the server.
  - The `state` parameter is used to prevent CSRF on the OAuth callback.
  - If a user is not logged in to University Finder, we still allow
    Facebook connection — the tokens are stored in their session.
"""

from __future__ import annotations

import secrets
import sys

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    request,
    session,
    url_for,
)

from services.facebook_service import (
    build_oauth_url,
    exchange_code_for_user_token,
    exchange_for_long_lived_user_token,
    fetch_user_pages,
    is_facebook_configured,
)


facebook_bp = Blueprint("facebook", __name__, url_prefix="/facebook")


# ============================================================
# GET /facebook/connect
# ============================================================

@facebook_bp.route("/connect")
def connect():
    """Redirect the user to the Facebook OAuth dialog."""
    if not is_facebook_configured():
        return jsonify({
            "error": "facebook_not_configured",
            "message": "Facebook integration is not enabled on this server.",
        }), 503

    # CSRF protection: random state stored in the session, verified on callback.
    state = secrets.token_urlsafe(24)
    session["facebook_oauth_state"] = state

    try:
        url = build_oauth_url(state=state)
    except Exception as exc:
        print(f"[facebook] build_oauth_url failed: {exc}", file=sys.stderr)
        return jsonify({
            "error": "oauth_url_failed",
            "message": "Could not start Facebook authorization.",
        }), 500

    return redirect(url)


# ============================================================
# GET /facebook/callback
# ============================================================

@facebook_bp.route("/callback")
def callback():
    """Handle the OAuth callback from Facebook."""
    error = request.args.get("error")
    if error:
        return jsonify({
            "error": "facebook_denied",
            "message": request.args.get("error_description") or error,
        }), 400

    code = request.args.get("code")
    state = request.args.get("state")
    expected_state = session.pop("facebook_oauth_state", None)

    if not code:
        return jsonify({
            "error": "missing_code",
            "message": "Facebook did not return an authorization code.",
        }), 400

    if not state or state != expected_state:
        return jsonify({
            "error": "invalid_state",
            "message": "OAuth state mismatch. Please try connecting again.",
        }), 400

    # --- Exchange code for short-lived user token ---
    try:
        short = exchange_code_for_user_token(code)
    except Exception as exc:
        print(f"[facebook] code exchange failed: {exc}", file=sys.stderr)
        return jsonify({
            "error": "token_exchange_failed",
            "message": str(exc),
        }), 502

    short_token = short.get("access_token")
    if not short_token:
        return jsonify({
            "error": "no_access_token",
            "message": "Facebook did not return an access token.",
        }), 502

    # --- Exchange short-lived for long-lived ---
    try:
        long_resp = exchange_for_long_lived_user_token(short_token)
        long_token = long_resp.get("access_token") or short_token
        expires_in = long_resp.get("expires_in")
    except Exception as exc:
        print(f"[facebook] long-lived exchange failed: {exc}", file=sys.stderr)
        # Fall back to short token — user will need to reconnect in ~2h.
        long_token = short_token
        expires_in = short.get("expires_in")

    # --- Fetch Pages the user administers ---
    pages = fetch_user_pages(long_token)

    # --- Persist in session ---
    session["facebook_user_token"] = long_token
    session["facebook_token_expires_in"] = expires_in
    session["facebook_pages"] = [
        {"id": p["id"], "name": p["name"], "access_token": p["access_token"]}
        for p in pages
    ]

    return jsonify({
        "status": "connected",
        "pages_count": len(pages),
        "pages": [
            {"id": p["id"], "name": p["name"]}
            for p in pages
        ],
    })


# ============================================================
# GET /facebook/status
# ============================================================

@facebook_bp.route("/status")
def status():
    """Return connection state for the frontend."""
    connected = bool(session.get("facebook_user_token"))
    pages = session.get("facebook_pages") or []
    return jsonify({
        "configured": is_facebook_configured(),
        "connected": connected,
        "pages_count": len(pages),
        "pages": [
            {"id": p["id"], "name": p["name"]}
            for p in pages
        ],
    })


# ============================================================
# POST /facebook/disconnect
# ============================================================

@facebook_bp.route("/disconnect", methods=["POST"])
def disconnect():
    """Clear stored Facebook tokens from the session."""
    session.pop("facebook_user_token", None)
    session.pop("facebook_token_expires_in", None)
    session.pop("facebook_pages", None)
    session.pop("facebook_oauth_state", None)
    return jsonify({"status": "disconnected"})
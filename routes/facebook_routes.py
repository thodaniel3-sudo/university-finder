"""
Facebook OAuth routes.

Endpoints:
  GET  /facebook/connect    — redirect the user to Facebook's OAuth dialog
  GET  /facebook/callback   — receive the OAuth code, exchange for tokens,
                              store Page tokens in the Flask session
  GET  /facebook/status     — JSON: whether the user is connected
  POST /facebook/disconnect — clear stored tokens from the session

CSRF protection (state parameter):
  We use a signed, self-verifying token instead of a session cookie.
  The token is created with itsdangerous (signed with SECRET_KEY) and
  contains a timestamp so it expires after 10 minutes. This works
  reliably over HTTP and HTTPS, on any browser, with no SameSite
  cookie issues.
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
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from services.facebook_service import (
    build_oauth_url,
    exchange_code_for_user_token,
    exchange_for_long_lived_user_token,
    fetch_user_pages,
    is_facebook_configured,
)


facebook_bp = Blueprint("facebook", __name__, url_prefix="/facebook")


# ============================================================
# Signed-state helpers
# ============================================================

_STATE_SALT = "facebook-oauth-state-v1"
_STATE_MAX_AGE_S = 600   # 10 minutes


def _serializer() -> URLSafeTimedSerializer:
    """Build a serializer keyed off the app SECRET_KEY."""
    return URLSafeTimedSerializer(
        secret_key=current_app.config["SECRET_KEY"],
        salt=_STATE_SALT,
    )


def _make_state() -> str:
    """Create a signed state token: <random>.<signature>.<timestamp>."""
    nonce = secrets.token_urlsafe(24)
    return _serializer().dumps(nonce)


def _verify_state(token: str) -> bool:
    """Verify a signed state token. Returns True if valid and fresh."""
    if not token:
        return False
    try:
        _serializer().loads(token, max_age=_STATE_MAX_AGE_S)
        return True
    except SignatureExpired:
        print("[facebook] state token expired", file=sys.stderr)
        return False
    except BadSignature:
        print("[facebook] state token signature invalid", file=sys.stderr)
        return False
    except Exception as exc:
        print(f"[facebook] state verify failed: {exc}", file=sys.stderr)
        return False


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

    state = _make_state()

    try:
        url = build_oauth_url(state=state)
    except Exception as exc:
        print(f"[facebook] build_oauth_url failed: {exc}", file=sys.stderr)
        return jsonify({
            "error": "oauth_url_failed",
            "message": "Could not start Facebook authorization.",
        }), 500

    return redirect(url)






@facebook_bp.route("/callback")
def callback():
    """Handle the OAuth callback from Facebook."""
    error = request.args.get("error")
    if error:
        return redirect(url_for(
            "search.search_view",
            facebook="denied",
        ))

    code = request.args.get("code")
    state = request.args.get("state")

    if not code:
        return redirect(url_for(
            "search.search_view",
            facebook="missing_code",
        ))

    if not _verify_state(state):
        return redirect(url_for(
            "search.search_view",
            facebook="invalid_state",
        ))

    # --- Exchange code for short-lived user token ---
    try:
        short = exchange_code_for_user_token(code)
    except Exception as exc:
        print(f"[facebook] code exchange failed: {exc}", file=sys.stderr)
        return redirect(url_for(
            "search.search_view",
            facebook="token_exchange_failed",
        ))

    short_token = short.get("access_token")
    if not short_token:
        return redirect(url_for(
            "search.search_view",
            facebook="no_token",
        ))

    # --- Exchange short-lived for long-lived ---
    try:
        long_resp = exchange_for_long_lived_user_token(short_token)
        long_token = long_resp.get("access_token") or short_token
        expires_in = long_resp.get("expires_in")
    except Exception as exc:
        print(f"[facebook] long-lived exchange failed: {exc}", file=sys.stderr)
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

    # Redirect back to the search page. The frontend JS reads
    # ?facebook=connected and refreshes the status card.
    return redirect(url_for("search.search_view", facebook="connected"))





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
    return jsonify({"status": "disconnected"})
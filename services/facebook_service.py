"""
Meta / Facebook source service.

Scope (officially supported by Meta Graph API):
  - OAuth 2.0 authentication (no passwords ever touch this app)
  - Read Pages the authenticating user administers
  - Read posts from those Pages

NOT supported by Meta's official API:
  - Keyword search across all Facebook posts
  - Searching arbitrary public Pages by name
  - Reading posts from Pages the user does not administer

This module handles:
  - Building the OAuth dialog URL
  - Exchanging the short-lived code for a user access token
  - Exchanging the short-lived user token for a long-lived one
  - Fetching Page access tokens via /me/accounts
  - Fetching posts from a Page via /{page-id}/posts
  - Normalizing post data to the app's common result format

All secrets (META_APP_SECRET) stay server-side. The frontend never
sees them.
"""

from __future__ import annotations

import sys
from typing import Any
from urllib.parse import urlencode

import httpx

from config import Config


# ============================================================
# Constants
# ============================================================

GRAPH_API_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
OAUTH_DIALOG_BASE = f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth"

# Permissions requested. Both are Standard Access for the user's own
# Pages. No App Review required.
OAUTH_SCOPES = [
    "public_profile",
    "pages_show_list",
    "pages_read_engagement",
]

HTTP_TIMEOUT = 15.0


# ============================================================
# Config helpers
# ============================================================

def _app_id() -> str:
    return (Config.META_APP_ID or "").strip()


def _app_secret() -> str:
    return (Config.META_APP_SECRET or "").strip()


def _redirect_uri() -> str:
    return (Config.META_REDIRECT_URI or "").strip()


def is_facebook_configured() -> bool:
    """Return True if all three Meta config values are present."""
    return bool(_app_id() and _app_secret() and _redirect_uri())


# ============================================================
# OAuth: build authorization URL
# ============================================================

def build_oauth_url(state: str | None = None) -> str:
    """
    Build the Facebook OAuth dialog URL.

    The user is redirected here. They enter their password on
    facebook.com — never on our site.
    """
    if not is_facebook_configured():
        raise RuntimeError(
            "Facebook is not configured. Set META_APP_ID, "
            "META_APP_SECRET, and META_REDIRECT_URI in .env."
        )

    params = {
        "client_id": _app_id(),
        "redirect_uri": _redirect_uri(),
        "scope": ",".join(OAUTH_SCOPES),
        "response_type": "code",
    }
    if state:
        params["state"] = state

    return f"{OAUTH_DIALOG_BASE}?{urlencode(params)}"


# ============================================================
# OAuth: exchange code -> short-lived user token
# ============================================================

def exchange_code_for_user_token(code: str) -> dict[str, Any]:
    """Exchange the OAuth callback code for a short-lived user token."""
    if not is_facebook_configured():
        raise RuntimeError("Facebook is not configured.")

    url = f"{GRAPH_BASE}/oauth/access_token"
    params = {
        "client_id": _app_id(),
        "client_secret": _app_secret(),
        "redirect_uri": _redirect_uri(),
        "code": code,
    }

    try:
        response = httpx.get(url, params=params, timeout=HTTP_TIMEOUT)
    except Exception as exc:
        print(f"[facebook] token exchange failed: {exc}", file=sys.stderr)
        raise RuntimeError("Could not reach Facebook to exchange the code.")

    if response.status_code != 200:
        print(
            f"[facebook] token exchange returned {response.status_code}: "
            f"{response.text[:300]}",
            file=sys.stderr,
        )
        raise RuntimeError(
            "Facebook rejected the authorization code. "
            "It may have expired or already been used."
        )

    return response.json()


# ============================================================
# OAuth: short-lived user token -> long-lived user token
# ============================================================

def exchange_for_long_lived_user_token(short_token: str) -> dict[str, Any]:
    """Exchange a short-lived user token (~2h) for a long-lived one (~60d)."""
    if not is_facebook_configured():
        raise RuntimeError("Facebook is not configured.")

    url = f"{GRAPH_BASE}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": _app_id(),
        "client_secret": _app_secret(),
        "fb_exchange_token": short_token,
    }

    try:
        response = httpx.get(url, params=params, timeout=HTTP_TIMEOUT)
    except Exception as exc:
        print(f"[facebook] long-lived exchange failed: {exc}", file=sys.stderr)
        raise RuntimeError("Could not reach Facebook to extend the token.")

    if response.status_code != 200:
        print(
            f"[facebook] long-lived exchange returned {response.status_code}: "
            f"{response.text[:300]}",
            file=sys.stderr,
        )
        raise RuntimeError("Facebook rejected the long-lived token request.")

    return response.json()


# ============================================================
# Pages the user administers
# ============================================================

def fetch_user_pages(user_token: str) -> list[dict[str, Any]]:
    """Return a list of Pages the user administers."""
    url = f"{GRAPH_BASE}/me/accounts"
    params = {
        "access_token": user_token,
        "fields": "id,name,access_token,category",
        "limit": 100,
    }

    try:
        response = httpx.get(url, params=params, timeout=HTTP_TIMEOUT)
    except Exception as exc:
        print(f"[facebook] /me/accounts failed: {exc}", file=sys.stderr)
        return []

    if response.status_code != 200:
        print(
            f"[facebook] /me/accounts returned {response.status_code}: "
            f"{response.text[:300]}",
            file=sys.stderr,
        )
        return []

    data = response.json().get("data") or []
    return [
        {
            "id": p.get("id"),
            "name": p.get("name") or "",
            "access_token": p.get("access_token") or "",
            "category": p.get("category") or "",
        }
        for p in data
        if p.get("id") and p.get("access_token")
    ]


# ============================================================
# Page posts
# ============================================================

def fetch_page_posts(page_id: str, page_token: str, limit: int = 25) -> list[dict[str, Any]]:
    """Return recent posts from a single Page."""
    url = f"{GRAPH_BASE}/{page_id}/posts"
    params = {
        "access_token": page_token,
        "fields": "id,message,created_time,permalink_url",
        "limit": min(max(1, limit), 100),
    }

    try:
        response = httpx.get(url, params=params, timeout=HTTP_TIMEOUT)
    except Exception as exc:
        print(f"[facebook] /{page_id}/posts failed: {exc}", file=sys.stderr)
        return []

    if response.status_code != 200:
        print(
            f"[facebook] /{page_id}/posts returned {response.status_code}: "
            f"{response.text[:300]}",
            file=sys.stderr,
        )
        return []

    data = response.json().get("data") or []
    results: list[dict[str, Any]] = []
    for post in data:
        permalink = post.get("permalink_url") or ""
        results.append({
            "id": post.get("id") or "",
            "message": post.get("message") or "",
            "created_time": post.get("created_time") or "",
            "permalink_url": permalink,
            "source_url": permalink,
            "source_type": "facebook",
        })
    return results


# ============================================================
# Top-level entry point
# ============================================================

def search_facebook(user_token: str, query: str, max_pages: int = 5,
                    posts_per_page: int = 25) -> list[dict[str, Any]]:
    """
    Fetch recent posts from the Pages the user administers and filter
    them client-side by the query terms.

    This is the only officially supported behavior. It does NOT do
    keyword search across Facebook.
    """
    if not user_token:
        return []

    query_terms = [t for t in (query or "").lower().split() if t]
    pages = fetch_user_pages(user_token)[:max_pages]

    results: list[dict[str, Any]] = []
    for page in pages:
        posts = fetch_page_posts(
            page_id=page["id"],
            page_token=page["access_token"],
            limit=posts_per_page,
        )
        for post in posts:
            message = (post.get("message") or "").lower()
            if query_terms and not any(t in message for t in query_terms):
                continue
            results.append({
                **post,
                "page_id": page["id"],
                "page_name": page["name"],
                "organization": page["name"],
                "title": (post.get("message") or "").split("\n", 1)[0][:200],
                "description": post.get("message") or "",
            })
    return results
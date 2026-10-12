"""
Reddit source service.

Uses the Reddit OAuth2 "application-only" flow (client_credentials) to
search public Reddit content for a query. No user login is required.

Quota safety:
  - OAuth token cached for 55 minutes (Reddit tokens last 60 minutes).
  - In-memory search cache, TTL 15 minutes.
  - Rate limiter: 2 seconds between search calls.
  - If credentials are missing, returns [] silently.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx

from config import Config


TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
SEARCH_URL = "https://oauth.reddit.com/search"

SEARCH_CACHE_TTL_S = 900        # 15 minutes
TOKEN_REFRESH_SAFETY_S = 300    # refresh 5 min before expiry
RATE_LIMIT_S = 2.0
HTTP_TIMEOUT = 15.0


# ------------------------------------------------------------
# Caches and locks
# ------------------------------------------------------------

_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_LOCK = threading.Lock()

_TOKEN_CACHE: dict[str, Any] = {"value": None, "expires_at": 0.0}
_TOKEN_LOCK = threading.Lock()

_LAST_CALL = [0.0]
_CALL_LOCK = threading.Lock()


# ------------------------------------------------------------
# Config helpers
# ------------------------------------------------------------

def _client_id() -> str:
    return (getattr(Config, "REDDIT_CLIENT_ID", "") or "").strip()


def _client_secret() -> str:
    return (getattr(Config, "REDDIT_CLIENT_SECRET", "") or "").strip()


def _user_agent() -> str:
    return (getattr(Config, "REDDIT_USER_AGENT", "") or "university-finder/1.0").strip()


def is_reddit_available() -> bool:
    """Return True if Reddit credentials are configured."""
    return bool(_client_id() and _client_secret())


# ------------------------------------------------------------
# OAuth token
# ------------------------------------------------------------

def _get_access_token() -> str | None:
    """Return a valid OAuth2 bearer token, refreshing if needed."""
    if not is_reddit_available():
        return None

    now = time.time()
    with _TOKEN_LOCK:
        cached = _TOKEN_CACHE.get("value")
        expires_at = _TOKEN_CACHE.get("expires_at", 0.0)
        if cached and expires_at - TOKEN_REFRESH_SAFETY_S > now:
            return cached

        try:
            response = httpx.post(
                TOKEN_URL,
                auth=(_client_id(), _client_secret()),
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": _user_agent()},
                timeout=HTTP_TIMEOUT,
            )
        except Exception as exc:
            print(f"[reddit] token request failed: {exc}")
            return None

        if response.status_code != 200:
            print(
                f"[reddit] token endpoint returned {response.status_code}: "
                f"{response.text[:200]}"
            )
            return None

        payload = response.json()
        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in") or 3600)

        if not token:
            print("[reddit] token response missing access_token")
            return None

        _TOKEN_CACHE["value"] = token
        _TOKEN_CACHE["expires_at"] = now + expires_in
        return token


# ------------------------------------------------------------
# Cache helpers
# ------------------------------------------------------------

def _cache_key(query: str) -> str:
    return (query or "").strip().lower()


def _cache_get(key: str) -> list[dict] | None:
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        expires_at, payload = entry
        if expires_at < time.time():
            _CACHE.pop(key, None)
            return None
        return payload


def _cache_put(key: str, payload: list[dict]) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = (time.time() + SEARCH_CACHE_TTL_S, payload)
        if len(_CACHE) > 200:
            now = time.time()
            for k in list(_CACHE.keys()):
                if _CACHE[k][0] < now:
                    _CACHE.pop(k, None)


# ------------------------------------------------------------
# Rate limiter
# ------------------------------------------------------------

def _rate_limit() -> None:
    with _CALL_LOCK:
        now = time.time()
        elapsed = now - _LAST_CALL[0]
        if elapsed < RATE_LIMIT_S:
            time.sleep(RATE_LIMIT_S - elapsed)
        _LAST_CALL[0] = time.time()


# ------------------------------------------------------------
# Normalization
# ------------------------------------------------------------

def _normalize(child: dict) -> dict[str, Any]:
    data = child.get("data") or {}
    permalink = data.get("permalink") or ""
    full_url = f"https://www.reddit.com{permalink}" if permalink else data.get("url") or ""

    selftext = data.get("selftext") or ""
    if len(selftext) > 600:
        selftext = selftext[:600] + "…"

    return {
        "id": data.get("id") or "",
        "title": data.get("title") or "",
        "subreddit": data.get("subreddit_name_prefixed") or data.get("subreddit") or "",
        "author": data.get("author") or "",
        "description": selftext,
        "url": full_url,
        "source_url": full_url,
        "score": data.get("score") or 0,
        "num_comments": data.get("num_comments") or 0,
        "created_utc": data.get("created_utc") or 0,
        "source_type": "reddit",
    }


# ------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------

def search_reddit(query: str, limit: int = 25) -> list[dict]:
    """
    Search Reddit for the query.

    Returns a list of normalized results, or [] on failure.
    """
    query = (query or "").strip()
    if not query or not is_reddit_available():
        return []

    key = _cache_key(query)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    token = _get_access_token()
    if not token:
        return []

    _rate_limit()

    params = {
        "q": query,
        "sort": "relevance",
        "limit": min(max(1, int(limit)), 100),
        "type": "link",
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": _user_agent(),
        "Accept": "application/json",
    }

    try:
        response = httpx.get(
            SEARCH_URL,
            params=params,
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
    except Exception as exc:
        print(f"[reddit] search request failed: {exc}")
        return []

    if response.status_code != 200:
        print(
            f"[reddit] search returned {response.status_code}: "
            f"{response.text[:200]}"
        )
        return []

    try:
        payload = response.json()
    except Exception:
        return []

    children = ((payload.get("data") or {}).get("children")) or []
    normalized = [_normalize(c) for c in children]

    _cache_put(key, normalized)
    return normalized
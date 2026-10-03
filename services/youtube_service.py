"""
YouTube source service.

Uses YouTube Data API v3 search.list to find videos related to a query.
Free tier: 100 search.list calls/day, 1 quota unit per call.
Returns normalized results compatible with the other search sources.

Quota safety:
  - 15-minute in-memory cache (same as Brave sources).
  - Rate limiter: 2 seconds between calls.
  - If no API key is configured, returns [] silently.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from config import Config


YOUTUBE_SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"

CACHE_TTL_S = 900           # 15 minutes
RATE_LIMIT_S = 2.0          # min gap between YouTube API calls

_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_LOCK = threading.Lock()

_LAST_CALL = [0.0]
_CALL_LOCK = threading.Lock()


def _get_api_key() -> str | None:
    raw = (getattr(Config, "YOUTUBE_API_KEY", "") or "").strip()
    if not raw:
        return None
    # Google API keys start with "AIza"
    if not raw.startswith("AIza"):
        return None
    return raw


def is_youtube_available() -> bool:
    return _get_api_key() is not None


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
        _CACHE[key] = (time.time() + CACHE_TTL_S, payload)
        if len(_CACHE) > 200:
            now = time.time()
            for k in list(_CACHE.keys()):
                if _CACHE[k][0] < now:
                    _CACHE.pop(k, None)


def _rate_limit() -> None:
    with _CALL_LOCK:
        now = time.time()
        elapsed = now - _LAST_CALL[0]
        if elapsed < RATE_LIMIT_S:
            time.sleep(RATE_LIMIT_S - elapsed)
        _LAST_CALL[0] = time.time()


def _channel_url(channel_id: str) -> str:
    if not channel_id:
        return ""
    return f"https://www.youtube.com/channel/{channel_id}"


def _domain_from_url(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().replace("www.", "")
    except Exception:
        return ""


def _search_videos(query: str, max_results: int = 25) -> list[dict]:
    """
    Call search.list once. Returns raw items or [].
    """
    api_key = _get_api_key()
    if not api_key:
        return []

    _rate_limit()

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": min(max(1, int(max_results)), 50),
        "key": api_key,
        "safeSearch": "moderate",
    }

    try:
        response = httpx.get(
            YOUTUBE_SEARCH_ENDPOINT,
            params=params,
            timeout=12.0,
        )
    except Exception as exc:
        print(f"[youtube] request failed: {exc}")
        return []

    if response.status_code != 200:
        print(
            f"[youtube] returned {response.status_code}: "
            f"{response.text[:200]}"
        )
        return []

    return (response.json().get("items") or [])


def _normalize(item: dict) -> dict[str, Any]:
    """
    Turn a search.list item into our common result shape.
    """
    snippet = item.get("snippet") or {}
    ident = item.get("id") or {}

    video_id = ident.get("videoId") or ""
    channel_id = snippet.get("channelId") or ""
    video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""

    thumbnails = snippet.get("thumbnails") or {}
    thumb = ""
    for size in ("medium", "high", "default"):
        if size in thumbnails and thumbnails[size].get("url"):
            thumb = thumbnails[size]["url"]
            break

    return {
        "title": snippet.get("title") or "",
        "organization": snippet.get("channelTitle") or "",
        "description": snippet.get("description") or "",
        "website_url": video_url,
        "source_url": video_url,
        "source_type": "youtube",
        "published_at": snippet.get("publishedAt") or "",
        "channel_id": channel_id,
        "channel_url": _channel_url(channel_id),
        "thumbnail": thumb,
        "domain": "youtube.com",
    }


def search_youtube(query: str, max_results: int = 25) -> list[dict]:
    """
    Public entry point.

    Returns a list of normalized YouTube results for the query.
    Uses the cache; on a miss, calls YouTube once.
    """
    query = (query or "").strip()
    if not query or not is_youtube_available():
        return []

    key = _cache_key(query)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    items = _search_videos(query, max_results=max_results)
    normalized = [_normalize(i) for i in items]

    _cache_put(key, normalized)
    return normalized
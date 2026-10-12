"""
Apify sources service — Course Catalog + Rate My Professors lookups.

This is a SEPARATE, INDEPENDENT integration from the Brave-based
extra_sources_service. It uses ONLY Apify.

Both sources are LOOKUP tools — they scrape specific URLs the user
provides. They are NOT general search engines.

Apify free plan includes $5 in monthly credits. Both actors are
pay-per-result. When credits run out, requests fail silently and the
UI shows a clear error.

Safety:
  - In-memory cache, TTL 60 minutes per URL.
  - Rate limiter: 3 seconds between Apify calls.
  - If APIFY_TOKEN is missing, all sources return a clear error dict.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx

from config import Config


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------

APIFY_RUN_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"

# Course catalog scraper — Data Pilot
COURSE_CATALOG_ACTOR = "datapilot~university-course-catalog-scraper"

# Rate My Professors scraper — Jungle Synthesizer (public GraphQL API)
RMP_ACTOR = "jungle_synthesizer~ratemyprofessors-professor-ratings-scraper"

CACHE_TTL_S = 3600            # 60 minutes
RATE_LIMIT_S = 3.0
HTTP_TIMEOUT = 120.0          # Apify actors can be slow
USER_AGENT = "university-finder/1.0 (educational)"


# ------------------------------------------------------------
# Cache + rate limiter
# ------------------------------------------------------------

_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_LOCK = threading.Lock()

_LAST_CALL = [0.0]
_CALL_LOCK = threading.Lock()


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
        if len(_CACHE) > 100:
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


def _apify_token() -> str:
    return (getattr(Config, "APIFY_TOKEN", "") or "").strip()


def is_apify_available() -> bool:
    return bool(_apify_token())


# ------------------------------------------------------------
# Shared Apify runner
# ------------------------------------------------------------

def _run_actor(actor_id: str, payload: dict) -> tuple[list[dict], str]:
    """
    Run an Apify actor synchronously and return (items, error_message).
    On success error_message is "".
    """
    if not is_apify_available():
        return [], "Apify token not configured. Add APIFY_TOKEN to .env."

    _rate_limit()

    url = APIFY_RUN_URL.format(actor=actor_id)

    try:
        response = httpx.post(
            url,
            params={"token": _apify_token()},
            json=payload,
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
    except Exception as exc:
        return [], f"Request failed: {exc}"

    if response.status_code not in (200, 201):
        text = response.text[:300]
        if response.status_code == 402:
            return [], "Apify free credits exhausted. Upgrade or wait for monthly reset."
        return [], f"Apify HTTP {response.status_code}: {text}"

    try:
        items = response.json()
    except Exception as exc:
        return [], f"JSON parse failed: {exc}"

    if not isinstance(items, list):
        return [], f"Unexpected payload type: {type(items).__name__}"

    if not items:
        return [], "Actor returned no results. The page may have no matching data."

    return [x for x in items if isinstance(x, dict)], ""


# ============================================================
# SOURCE 1 — UNIVERSITY COURSE CATALOG (LOOKUP)
# ============================================================

def _normalize_course(item: dict) -> dict[str, Any]:
    return {
        "id": item.get("course_code") or item.get("title") or "",
        "title": item.get("title") or "Untitled Course",
        "course_code": item.get("course_code") or "",
        "credits": item.get("credits") or "",
        "department": item.get("department") or "",
        "description": (item.get("description") or "")[:500],
        "prerequisites": item.get("prerequisites") or "",
        "url": item.get("source_url") or "",
        "source_url": item.get("source_url") or "",
        "source_type": "course",
    }


def lookup_course_catalog(catalog_url: str, max_courses: int = 50) -> tuple[list[dict], str]:
    """
    Scrape a university course catalog page.

    Args:
        catalog_url: Full URL of a university course catalog page
        max_courses: Maximum number of courses to collect

    Returns:
        (normalized_courses, error_message). error_message is "" on success.
    """
    catalog_url = (catalog_url or "").strip()
    if not catalog_url:
        return [], "Please provide a university course catalog URL."
    if not catalog_url.startswith("http"):
        return [], "URL must start with http:// or https://"

    key = f"course::{catalog_url}"
    cached = _cache_get(key)
    if cached is not None:
        return cached, ""

    payload = {
        "url": catalog_url,
        "maxCourses": min(max(1, int(max_courses)), 500),
        "waitSeconds": 5,
        "useApifyProxy": True,
        "apifyProxyGroups": ["RESIDENTIAL"],
    }

    items, err = _run_actor(COURSE_CATALOG_ACTOR, payload)
    if err:
        return [], err

    normalized = [_normalize_course(x) for x in items]
    _cache_put(key, normalized)
    return normalized, ""


# ============================================================
# SOURCE 2 — RATE MY PROFESSORS (LOOKUP)
# ============================================================

def _normalize_professor(item: dict) -> dict[str, Any]:
    """Normalize a Rate My Professors record."""
    # RMP returns flat rows — map common fields
    name = item.get("name") or item.get("professorName") or item.get("professor_name") or ""
    school = item.get("school") or item.get("schoolName") or item.get("school_name") or ""
    dept = item.get("department") or item.get("dept") or ""

    rating = (
        item.get("avgRating")
        or item.get("avg_rating")
        or item.get("rating")
        or item.get("overall_rating")
        or ""
    )
    difficulty = (
        item.get("avgDifficulty")
        or item.get("avg_difficulty")
        or item.get("difficulty")
        or ""
    )
    num_ratings = (
        item.get("numRatings")
        or item.get("num_ratings")
        or item.get("ratings_count")
        or 0
    )

    url = (
        item.get("url")
        or item.get("profileUrl")
        or item.get("profile_url")
        or item.get("link")
        or ""
    )

    return {
        "id": url or f"{name}::{school}",
        "title": name or "Unknown Professor",
        "school": school,
        "department": dept,
        "rating": rating,
        "difficulty": difficulty,
        "num_ratings": num_ratings,
        "description": f"{dept} · {school}".strip(" ·"),
        "url": url,
        "source_url": url,
        "source_type": "professor",
    }


def lookup_professors(search_url: str, max_items: int = 25) -> tuple[list[dict], str]:
    """
    Scrape Rate My Professors from a search URL.

    Args:
        search_url: A Rate My Professors search URL (e.g. https://www.ratemyprofessors.com/search/professors?q=math)
        max_items: Maximum number of professors to collect

    Returns:
        (normalized_professors, error_message). error_message is "" on success.
    """
    search_url = (search_url or "").strip()
    if not search_url:
        return [], "Please provide a Rate My Professors search URL."
    if "ratemyprofessors.com" not in search_url:
        return [], "URL must be a ratemyprofessors.com search URL."
    if not search_url.startswith("http"):
        return [], "URL must start with http:// or https://"

    key = f"rmp::{search_url}"
    cached = _cache_get(key)
    if cached is not None:
        return cached, ""

    # This actor accepts school names or IDs. We'll send the URL as input
    # and let it extract the search parameters.
    payload = {
        "urls": [search_url],
        "maxItems": min(max(1, int(max_items)), 100),
    }

    items, err = _run_actor(RMP_ACTOR, payload)
    if err:
        return [], err

    normalized = [_normalize_professor(x) for x in items]
    _cache_put(key, normalized)
    return normalized, ""


# ============================================================
# Availability
# ============================================================

def source_availability() -> dict[str, bool]:
    return {
        "available": is_apify_available(),
    }
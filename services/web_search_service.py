"""
Brave Search API wrapper.

This module calls the Brave Search REST API to find university programmes
on the open web. It is used as a fallback when our curated database has
no match.

Design principles:
  - Never scrape university sites directly. We only display search
    results with title, URL, and snippet.
  - Results are clearly labeled as "not verified" in the UI.
  - If the API key is missing, we return an empty list and let the
    caller show a graceful fallback message.

Sign up for a free key: https://brave.com/search/api/
"""

from typing import Any

import httpx

from config import Config


BRAVE_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


# ------------------------------------------------------------
# Key validation
# ------------------------------------------------------------

# Reject values that look like placeholders from .env.example files.
_PLACEHOLDER_KEYS = {
    "your-key-here",
    "your-api-key",
    "replace-me",
    "changeme",
    "insert-key-here",
}


def _get_api_key() -> str | None:
    """
    Return the stripped Brave API key, or None if not usable.

    Guards against:
      - Empty values
      - Whitespace-only values
      - Placeholder text like "your-key-here"
      - Values that don't look like real Brave keys
    """
    raw = (Config.BRAVE_SEARCH_API_KEY or "").strip()
    if not raw:
        return None

    if raw.lower() in _PLACEHOLDER_KEYS:
        return None

    # A real Brave key always starts with "BSA".
    if not raw.startswith("BSA"):
        return None

    return raw


def is_web_search_available() -> bool:
    """Return True if a usable Brave API key is configured."""
    return _get_api_key() is not None


# ------------------------------------------------------------
# Search
# ------------------------------------------------------------

def search_web(query: str, count: int = 8) -> list[dict[str, Any]]:
    """
    Search the web for the given query via Brave Search.

    Returns a list of results with:
        {
          "title": str,
          "url": str,
          "description": str,
          "source": str,   # the domain, e.g. "uib.no"
        }

    Returns an empty list if the key is missing, the request fails,
    or the API rejects the query.
    """
    api_key = _get_api_key()
    if not api_key:
        return []

    query = (query or "").strip()
    if not query:
        return []

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }
    params = {
        "q": query,
        "count": count,
        "safesearch": "moderate",
        "text_decorations": "0",
        "result_filter": "web",
    }

    # --- HTTP call ---
    try:
        response = httpx.get(
            BRAVE_SEARCH_ENDPOINT,
            headers=headers,
            params=params,
            timeout=8.0,
        )
    except Exception as exc:
        import sys
        print(f"[web_search] request failed: {exc}", file=sys.stderr)
        return []

    # --- Handle non-200 responses ---
    if response.status_code != 200:
        import sys
        print(
            f"[web_search] Brave returned {response.status_code}: "
            f"{response.text[:200]}",
            file=sys.stderr,
        )
        return []

    # --- Parse response ---
    try:
        payload = response.json()
    except Exception:
        return []

    web_results = (payload.get("web") or {}).get("results") or []

    results: list[dict[str, Any]] = []
    for item in web_results:
        url = item.get("url") or ""
        domain = ""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.replace("www.", "")
        except Exception:
            pass

        results.append({
            "title": item.get("title") or "",
            "url": url,
            "description": item.get("description") or "",
            "source": domain,
        })

    return results
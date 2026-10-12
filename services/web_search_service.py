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
  - Study-focused query enrichment: queries are rewritten with words like
    "master programme", "bachelor degree", "admission requirements"
    so Brave returns study-related pages, not encyclopedia entries.
  - Noise filter: Wikipedia, dictionaries, journal home pages, YouTube
    explainers, and job boards are excluded.
  - Deduplication: any URL already produced by the /extra/ Brave tabs is
    removed from this panel so no result appears twice.

Sign up for a free key: https://brave.com/search/api/
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from config import Config


BRAVE_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


# ------------------------------------------------------------
# Key validation
# ------------------------------------------------------------

_PLACEHOLDER_KEYS = {
    "your-key-here",
    "your-api-key",
    "replace-me",
    "changeme",
    "insert-key-here",
}


def _get_api_key() -> str | None:
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
    return _get_api_key() is not None


# ------------------------------------------------------------
# Noise filter — domains that are never useful for study search
# ------------------------------------------------------------

BLOCKED_DOMAINS = {
    # Encyclopedias / dictionaries
    "wikipedia.org",
    "en.wikipedia.org",
    "dictionary.com",
    "cambridge.org",
    "dictionary.cambridge.org",
    "merriam-webster.com",
    "thesaurus.com",
    "britannica.com",
    "collinsdictionary.com",
    "vocabulary.com",
    # Journal home pages / publishers (not programme pages)
    "mdpi.com",
    "nature.com",
    "sciencedirect.com",
    "pubs.acs.org",
    "acs.org",
    "elsevier.com",
    "springer.com",
    "wiley.com",
    "tandfonline.com",
    "researchgate.net",
    "semanticscholar.org",
    "arxiv.org",
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    # Video explainers / generic reference
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "pinterest.com",
    "quora.com",
    # Job boards
    "glassdoor.com",
    "indeed.com",
    "linkedin.com",
    # Commercial shopping
    "amazon.com",
    "ebay.com",
    "aliexpress.com",
    # Social
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "tiktok.com",
}


def _is_blocked(domain: str) -> bool:
    """Return True if the domain (or any parent domain) is blocked."""
    if not domain:
        return False
    d = domain.lower()
    for blocked in BLOCKED_DOMAINS:
        if d == blocked or d.endswith("." + blocked):
            return True
    return False


# ------------------------------------------------------------
# Domain prioritization — study portals rank first
# ------------------------------------------------------------

PRIORITY_DOMAINS = {
    # Study portals
    "daad.de",
    "mastersportal.com",
    "bachelorsportal.com",
    "phdportal.com",
    "studyportals.com",
    "findamasters.com",
    "findaphd.com",
    "study.eu",
    "study-in-germany.org",
    "studying-in-germany.org",
    "topuniversities.com",
    "timeshighereducation.com",
    "shanghairanking.com",
    "4icu.org",
    # Scholarship portals
    "scholarships.com",
    "fastweb.com",
    "collegeboard.org",
    "scholarshipportal.com",
    "chevening.org",
    # Government / official
    "europa.eu",
    "gov.uk",
    "usa.gov",
    "canada.ca",
}


def _priority_score(domain: str) -> int:
    """Lower score = higher priority. Used for stable sorting."""
    if not domain:
        return 2
    d = domain.lower()

    for p in PRIORITY_DOMAINS:
        if d == p or d.endswith("." + p):
            return 0

    # University domains
    if d.endswith(".edu") or ".edu." in d:
        return 1
    if d.endswith(".ac.uk") or ".ac." in d:
        return 1
    if d.endswith(".uni-") or ".university" in d:
        return 1

    return 2


# ------------------------------------------------------------
# Query enrichment
# ------------------------------------------------------------

STUDY_KEYWORDS = "master OR bachelor OR PhD programme degree admission"


def _enrich_query(raw_query: str) -> str:
    """
    Turn a raw student query into a study-focused web query.

    Example:
        "materials science germany"
        → "materials science germany master OR bachelor OR PhD programme degree admission"
    """
    q = (raw_query or "").strip()
    if not q:
        return ""

    # If the query already contains study words, don't double them.
    lowered = q.lower()
    study_words = ("programme", "program", "degree", "master", "bachelor", "phd", "admission")
    if any(w in lowered for w in study_words):
        return q

    return f"{q} {STUDY_KEYWORDS}"


# ------------------------------------------------------------
# Core search (unchanged public API)
# ------------------------------------------------------------

def search_web(
    query: str,
    count: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Search the web for the given query via Brave Search.

    `offset` is the number of results to skip. Brave uses 0-indexed offsets
    and caps `offset + count` at 200 total results.

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

    if offset >= 200:
        return []

    if offset + count > 200:
        count = 200 - offset

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }
    params = {
        "q": query,
        "count": count,
        "offset": offset,
        "safesearch": "moderate",
        "text_decorations": "0",
        "result_filter": "web",
    }

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

    if response.status_code != 200:
        import sys
        print(
            f"[web_search] Brave returned {response.status_code}: "
            f"{response.text[:200]}",
            file=sys.stderr,
        )
        return []

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


# ------------------------------------------------------------
# Filtered search — used by the "From the open web" panel
# ------------------------------------------------------------

def search_web_filtered(
    query: str,
    count: int = 20,
    offset: int = 0,
    exclude_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Study-focused web search with noise filtering + deduplication.

    Steps:
      1. Enrich the query with study keywords.
      2. Call Brave.
      3. Drop any result on a blocked domain.
      4. Drop any URL already present in `exclude_urls`
         (e.g. results already shown by the /extra/ Brave tabs).
      5. Sort by domain priority (study portals first, then .edu/.ac.uk,
         then everything else).

    Args:
        query: student query, e.g. "materials science germany"
        count: max results to fetch from Brave
        offset: pagination offset
        exclude_urls: set of URLs to remove from the output

    Returns:
        A cleaned, deduplicated, prioritized list of results.
    """
    exclude_urls = exclude_urls or set()

    enriched = _enrich_query(query)
    if not enriched:
        return []

    # Fetch a wider pool from Brave so filtering still leaves enough results.
    wide_pool = min(max(count * 3, 30), 100)
    raw = search_web(enriched, count=wide_pool, offset=offset)

    seen: set[str] = set()
    cleaned: list[dict[str, Any]] = []

    for r in raw:
        url = r.get("url") or ""
        domain = r.get("source") or ""
        if not url:
            continue
        if url in seen or url in exclude_urls:
            continue
        if _is_blocked(domain):
            continue
        seen.add(url)
        cleaned.append(r)

    cleaned.sort(key=lambda r: _priority_score(r.get("source") or ""))

    return cleaned[:count]


# ------------------------------------------------------------
# Convenience: compute exclusion set from /extra/ results
# ------------------------------------------------------------

def urls_from_extra_results(results: list[dict]) -> set[str]:
    """
    Extract URLs from a list of /extra/ results (scholarships,
    universities, programmes) so they can be excluded from the
    open-web panel.
    """
    urls: set[str] = set()
    for r in results or []:
        u = r.get("url") or r.get("source_url") or ""
        if u:
            urls.add(u)
    return urls
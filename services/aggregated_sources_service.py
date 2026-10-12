"""
Aggregated sources service — News, Identity, Research, Publications.

All four sources live in ONE file.
Each is isolated, cached, and rate-limited independently.

Sources:
  1. News         — Google News RSS          (free, no key)
  2. Identity     — Wikipedia + Wikidata     (free, no key)
  3. Research     — OpenAlex API             (free, no key)
  4. Publications — Crossref API             (free, no key)

Safety:
  - In-memory cache, TTL 30 minutes per source.
  - Rate limiter: 1 second minimum per source.
  - All sources return [] on any error, never raise.
"""

from __future__ import annotations

import html as _html
import re
import threading
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from config import Config


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
OPENALEX_URL = "https://api.openalex.org/works"
CROSSREF_URL = "https://api.crossref.org/works"

CACHE_TTL_S = 1800
RATE_LIMIT_S = 1.0
HTTP_TIMEOUT = 20.0
USER_AGENT = (
    "university-finder/1.0 "
    "(educational, non-commercial; mailto:university-finder@example.com)"
)


# ------------------------------------------------------------
# Shared cache + rate limiter
# ------------------------------------------------------------

_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_LOCK = threading.Lock()

_LAST_CALL = {"news": 0.0, "wiki": 0.0, "openalex": 0.0, "crossref": 0.0}
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
        if len(_CACHE) > 300:
            now = time.time()
            for k in list(_CACHE.keys()):
                if _CACHE[k][0] < now:
                    _CACHE.pop(k, None)


def _rate_limit(bucket: str) -> None:
    with _CALL_LOCK:
        now = time.time()
        elapsed = now - _LAST_CALL.get(bucket, 0.0)
        if elapsed < RATE_LIMIT_S:
            time.sleep(RATE_LIMIT_S - elapsed)
        _LAST_CALL[bucket] = time.time()


# ------------------------------------------------------------
# HTML cleanup helper (used by News + Publications)
# ------------------------------------------------------------

def _strip_html(text: str) -> str:
    """
    Remove HTML tags AND decode HTML entities.

    Google News wraps its RSS <description> in escaped HTML
    (&lt;a href=...&gt;). We must:
      1. Decode entities first (so &lt;a&gt; becomes <a>)
      2. Then strip the tags that appear
      3. Collapse extra whitespace
    """
    if not text:
        return ""
    decoded = _html.unescape(text)
    no_tags = re.sub(r"<[^>]+>", " ", decoded)
    cleaned = re.sub(r"\s+", " ", no_tags).strip()
    return cleaned


# ============================================================
# SOURCE 1 — NEWS (Google News RSS)
# ============================================================

def is_news_available() -> bool:
    return True


def _parse_rss(xml_text: str, limit: int) -> list[dict]:
    """Minimal RSS parser — no external dependency needed."""
    items: list[dict] = []

    blocks = re.findall(r"<item>(.*?)</item>", xml_text, flags=re.DOTALL)
    for block in blocks[:limit]:
        def _tag(name: str) -> str:
            m = re.search(
                rf"<{name}[^>]*>(.*?)</{name}>",
                block,
                flags=re.DOTALL,
            )
            if not m:
                return ""
            val = m.group(1)
            cdata = re.search(
                r"<!\[CDATA\[(.*?)\]\]>", val, flags=re.DOTALL
            )
            if cdata:
                val = cdata.group(1)
            return _strip_html(val)

        title = _tag("title")
        link = _tag("link")
        description = _tag("description")
        pub_date = _tag("pubDate")
        source = _tag("source")

        if not title or not link:
            continue

        try:
            domain = urlparse(link).netloc.replace("www.", "")
        except Exception:
            domain = ""

        items.append({
            "id": link,
            "title": title,
            "url": link,
            "source_url": link,
            "description": description[:500],
            "pub_date": pub_date,
            "provider": source or domain,
            "source_type": "news",
        })

    return items


def search_news(query: str, limit: int = 20) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []

    key = f"news::{query.lower()}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    _rate_limit("news")

    params = {
        "q": f"{query} university",
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }

    try:
        response = httpx.get(
            GOOGLE_NEWS_RSS,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
            follow_redirects=True,
        )
    except Exception as exc:
        print(f"[news] request failed: {exc}")
        return []

    if response.status_code != 200:
        print(f"[news] returned {response.status_code}")
        return []

    items = _parse_rss(response.text, min(max(1, int(limit)), 50))
    if items:
        _cache_put(key, items)
        print(f"[news] returned {len(items)} items")
    return items


# ============================================================
# SOURCE 2 — IDENTITY (Wikipedia + Wikidata)
# ============================================================

def is_identity_available() -> bool:
    return True


def _fetch_wikipedia_summary(title: str) -> dict | None:
    _rate_limit("wiki")
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts|pageimages|info",
        "inprop": "url",
        "exintro": 1,
        "explaintext": 1,
        "piprop": "thumbnail",
        "pithumbsize": 400,
        "titles": title,
        "redirects": 1,
    }
    try:
        r = httpx.get(
            WIKIPEDIA_API,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception as exc:
        print(f"[identity] wikipedia failed: {exc}")
        return None

    pages = (data.get("query") or {}).get("pages") or {}
    for _, page in pages.items():
        if "missing" in page:
            return None
        return {
            "title": page.get("title") or title,
            "extract": (page.get("extract") or "")[:600],
            "url": page.get("fullurl") or "",
            "thumbnail": ((page.get("thumbnail") or {}).get("source")) or "",
        }
    return None


def _fetch_wikidata(title: str) -> dict | None:
    _rate_limit("wiki")

    try:
        r = httpx.get(
            WIKIDATA_API,
            params={
                "action": "wbgetentities",
                "format": "json",
                "sites": "enwiki",
                "titles": title,
                "props": "claims|labels|descriptions",
                "languages": "en",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception as exc:
        print(f"[identity] wikidata failed: {exc}")
        return None

    entities = data.get("entities") or {}
    for _, ent in entities.items():
        if "missing" in ent:
            continue
        claims = ent.get("claims") or {}

        def _first_claim(prop: str):
            arr = claims.get(prop) or []
            if not arr:
                return None
            try:
                mainsnak = arr[0].get("mainsnak") or {}
                datavalue = mainsnak.get("datavalue") or {}
                return datavalue.get("value")
            except Exception:
                return None

        country = _first_claim("P17")
        inception = _first_claim("P571")
        website = _first_claim("P856")

        description = (
            (ent.get("descriptions") or {}).get("en") or {}
        ).get("value") or ""
        label = (
            (ent.get("labels") or {}).get("en") or {}
        ).get("value") or title

        return {
            "wikidata_id": ent.get("id") or "",
            "label": label,
            "description": description,
            "country_qid": country.get("id") if isinstance(country, dict) else "",
            "inception": inception.get("time") if isinstance(inception, dict) else "",
            "website": website if isinstance(website, str) else "",
        }

    return None


def search_identity(query: str, limit: int = 5) -> list[dict]:
    """Return one identity card for the best matching entity."""
    query = (query or "").strip()
    if not query:
        return []

    key = f"identity::{query.lower()}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    _rate_limit("wiki")
    try:
        r = httpx.get(
            WIKIPEDIA_API,
            params={
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "srlimit": 3,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        hits = (
            ((r.json().get("query") or {}).get("search")) or []
        ) if r.status_code == 200 else []
    except Exception:
        hits = []

    if not hits:
        return []

    title = hits[0].get("title") or ""
    if not title:
        return []

    summary = _fetch_wikipedia_summary(title)
    if not summary:
        return []

    wikidata = _fetch_wikidata(title) or {}

    card = {
        "id": f"identity::{title}",
        "title": summary["title"],
        "url": summary.get("url") or "",
        "source_url": summary.get("url") or "",
        "description": summary.get("extract") or "",
        "thumbnail": summary.get("thumbnail") or "",
        "wikidata_id": wikidata.get("wikidata_id") or "",
        "wikidata_description": wikidata.get("description") or "",
        "country_qid": wikidata.get("country_qid") or "",
        "inception": wikidata.get("inception") or "",
        "website": wikidata.get("website") or "",
        "source_type": "identity",
    }

    result = [card]
    _cache_put(key, result)
    print(f"[identity] returned identity for '{title}'")
    return result


# ============================================================
# SOURCE 3 — RESEARCH (OpenAlex)
# ============================================================

def is_research_available() -> bool:
    return True


def _normalize_work(item: dict) -> dict[str, Any]:
    authors = item.get("authorships") or []
    author_names = []
    for a in authors[:4]:
        name = ((a.get("author") or {}).get("display_name")) or ""
        if name:
            author_names.append(name)
    author_str = ", ".join(author_names)
    if len(authors) > 4:
        author_str += ", et al."

    host = (item.get("primary_location") or {}).get("source") or {}
    venue = host.get("display_name") or ""

    abstract = item.get("abstract_inverted_index")
    abstract_text = ""
    if isinstance(abstract, dict):
        words: dict[int, str] = {}
        for word, positions in abstract.items():
            for p in positions:
                words[p] = word
        abstract_text = " ".join(words[i] for i in sorted(words.keys()))
        if len(abstract_text) > 500:
            abstract_text = abstract_text[:500] + "…"

    return {
        "id": (item.get("id") or "").replace("https://openalex.org/", ""),
        "title": item.get("display_name") or "Untitled",
        "authors": author_str,
        "venue": venue,
        "year": item.get("publication_year") or "",
        "cited_by": item.get("cited_by_count") or 0,
        "doi": item.get("doi") or "",
        "url": item.get("doi") or item.get("id") or "",
        "source_url": item.get("doi") or item.get("id") or "",
        "description": abstract_text,
        "source_type": "research",
    }


def search_research(query: str, limit: int = 20) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []

    key = f"research::{query.lower()}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    _rate_limit("openalex")

    params = {
        "search": query,
        "per-page": min(max(1, int(limit)), 50),
        "sort": "relevance_score:desc",
        "mailto": "university-finder@example.com",
    }

    try:
        response = httpx.get(
            OPENALEX_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
    except Exception as exc:
        print(f"[research] request failed: {exc}")
        return []

    if response.status_code != 200:
        print(f"[research] returned {response.status_code}")
        return []

    try:
        payload = response.json()
    except Exception:
        return []

    results = payload.get("results") or []
    normalized = [_normalize_work(x) for x in results if isinstance(x, dict)]
    _cache_put(key, normalized)
    print(f"[research] returned {len(normalized)} items")
    return normalized


# ============================================================
# SOURCE 4 — PUBLICATIONS (Crossref)
# ============================================================

def is_publications_available() -> bool:
    return True


def _normalize_crossref(item: dict) -> dict[str, Any]:
    title_list = item.get("title") or []
    title = title_list[0] if title_list else "Untitled"

    authors = item.get("author") or []
    names = []
    for a in authors[:4]:
        given = a.get("given") or ""
        family = a.get("family") or ""
        full = f"{given} {family}".strip()
        if full:
            names.append(full)
    author_str = ", ".join(names)
    if len(authors) > 4:
        author_str += ", et al."

    container = item.get("container-title") or []
    venue = container[0] if container else ""

    issued = item.get("issued") or {}
    date_parts = issued.get("date-parts") or []
    year = ""
    if date_parts and isinstance(date_parts[0], list) and date_parts[0]:
        year = str(date_parts[0][0])

    doi = item.get("DOI") or ""
    url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")

    abstract = item.get("abstract") or ""
    abstract = _strip_html(abstract)
    if len(abstract) > 500:
        abstract = abstract[:500] + "…"

    return {
        "id": doi or url,
        "title": title,
        "authors": author_str,
        "venue": venue,
        "year": year,
        "doi": doi,
        "url": url,
        "source_url": url,
        "description": abstract,
        "cited_by": item.get("is-referenced-by-count") or 0,
        "source_type": "publication",
    }


def search_publications(query: str, limit: int = 20) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []

    key = f"publications::{query.lower()}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    _rate_limit("crossref")

    params = {
        "query": query,
        "rows": min(max(1, int(limit)), 50),
        "select": (
            "DOI,title,author,container-title,issued,URL,abstract,"
            "is-referenced-by-count"
        ),
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        response = httpx.get(
            CROSSREF_URL,
            params=params,
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
    except Exception as exc:
        print(f"[publications] request failed: {exc}")
        return []

    if response.status_code != 200:
        print(f"[publications] returned {response.status_code}")
        return []

    try:
        payload = response.json()
    except Exception:
        return []

    items = ((payload.get("message") or {}).get("items")) or []
    normalized = [_normalize_crossref(x) for x in items if isinstance(x, dict)]
    _cache_put(key, normalized)
    print(f"[publications] returned {len(normalized)} items")
    return normalized


# ============================================================
# Availability summary
# ============================================================

def source_availability() -> dict[str, bool]:
    return {
        "news": is_news_available(),
        "identity": is_identity_available(),
        "research": is_research_available(),
        "publications": is_publications_available(),
    }
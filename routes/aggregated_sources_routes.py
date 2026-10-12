"""
Aggregated sources routes — one page, four tabs.

Endpoints:
  GET /aggregated/                — renders the page
  GET /aggregated/api/news        — Google News RSS
  GET /aggregated/api/identity    — Wikipedia + Wikidata
  GET /aggregated/api/research    — OpenAlex
  GET /aggregated/api/publications — Crossref
"""

from flask import Blueprint, jsonify, render_template, request

from services.aggregated_sources_service import (
    search_identity,
    search_news,
    search_publications,
    search_research,
    source_availability,
)


aggregated_bp = Blueprint("aggregated", __name__, url_prefix="/aggregated")


@aggregated_bp.route("/")
def index():
    query = (request.args.get("q") or "").strip()
    tab = (request.args.get("tab") or "news").strip().lower()
    if tab not in ("news", "identity", "research", "publications"):
        tab = "news"

    return render_template(
        "aggregated_sources.html",
        query=query,
        active_tab=tab,
        availability=source_availability(),
    )


def _empty():
    return jsonify({"query": "", "results": [], "total": 0})


@aggregated_bp.route("/api/news")
def api_news():
    q = (request.args.get("q") or "").strip()
    if not q:
        return _empty()
    results = search_news(q, limit=25)
    return jsonify({"query": q, "results": results, "total": len(results)})


@aggregated_bp.route("/api/identity")
def api_identity():
    q = (request.args.get("q") or "").strip()
    if not q:
        return _empty()
    results = search_identity(q, limit=5)
    return jsonify({"query": q, "results": results, "total": len(results)})


@aggregated_bp.route("/api/research")
def api_research():
    q = (request.args.get("q") or "").strip()
    if not q:
        return _empty()
    results = search_research(q, limit=25)
    return jsonify({"query": q, "results": results, "total": len(results)})


@aggregated_bp.route("/api/publications")
def api_publications():
    q = (request.args.get("q") or "").strip()
    if not q:
        return _empty()
    results = search_publications(q, limit=25)
    return jsonify({"query": q, "results": results, "total": len(results)})
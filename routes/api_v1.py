"""
Versioned JSON API for the multi-source search.

Endpoints:
  GET  /api/v1/health   — service health + which sources are configured
  POST /api/v1/search   — run a multi-source search

Request body for POST /api/v1/search:
    {
      "query": "materials science germany",
      "sources": ["supabase", "brave", "university", "facebook"],
      "page": 1,
      "per_page": 20
    }

All responses are JSON. Errors return {"error": "...", "message": "..."}.

Secrets never appear in responses. Facebook is only queried when the
current user's session contains a Facebook token (set by /facebook/connect).
"""

from __future__ import annotations

import sys

from flask import Blueprint, jsonify, request

from services.search_service import search_multi_source
from services.facebook_service import is_facebook_configured
from services.web_search_service import is_web_search_available


api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


VALID_SOURCES = {"supabase", "brave", "university", "facebook"}


# ============================================================
# GET /api/v1/health
# ============================================================

@api_v1_bp.route("/health", methods=["GET"])
def health():
    """Health check + which sources are configured."""
    return jsonify({
        "status": "ok",
        "sources": {
            "supabase": True,
            "brave": is_web_search_available(),
            "university": is_web_search_available(),
            "facebook": is_facebook_configured(),
        },
    })


# ============================================================
# POST /api/v1/search
# ============================================================

@api_v1_bp.route("/search", methods=["POST"])
def search():
    """Run a multi-source search and return unified results."""
    try:
        payload = request.get_json(silent=True) or {}
    except Exception:
        payload = {}

    query = (payload.get("query") or "").strip()
    if not query:
        return jsonify({
            "error": "missing_query",
            "message": "Provide a non-empty 'query' string.",
        }), 400

    requested = payload.get("sources")
    if requested is None:
        sources = ["supabase", "brave", "university", "facebook"]
    else:
        if not isinstance(requested, list):
            return jsonify({
                "error": "invalid_sources",
                "message": "'sources' must be a list of strings.",
            }), 400
        sources = [s for s in requested if s in VALID_SOURCES]
        if not sources:
            return jsonify({
                "error": "no_valid_sources",
                "message": f"Provide at least one of: {sorted(VALID_SOURCES)}",
            }), 400

    try:
        page = max(1, int(payload.get("page") or 1))
    except (TypeError, ValueError):
        page = 1

    try:
          per_page = min(100, max(1, int(payload.get("per_page") or 20)))
    except (TypeError, ValueError):
        per_page = 20

    try:
        out = search_multi_source(
            query=query,
            sources=sources,
            page=page,
            per_page=per_page,
        )
    except Exception as exc:
        print(f"[api_v1] search failed: {exc}", file=sys.stderr)
        return jsonify({
            "error": "search_failed",
            "message": "The search pipeline encountered an error.",
        }), 500

    return jsonify({
        "query": out["query"],
        "page": page,
        "per_page": per_page,
        "total": out["total"],
        "results": out["results"],
        "sources": out["sources"],
    })
"""
Extra sources routes — one page, four tabs.

Endpoints:
  GET /extra/search           — renders the page
  GET /extra/api/scholarships — JSON for Scholarships
  GET /extra/api/research     — JSON for Research
  GET /extra/api/universities — JSON for Universities
  GET /extra/api/programmes   — JSON for Programmes
"""

from flask import Blueprint, jsonify, render_template, request

from services.extra_sources_service import (
    search_programmes,
    search_research,
    search_scholarships,
    search_universities,
    source_availability,
)


extra_bp = Blueprint("extra", __name__, url_prefix="/extra")


@extra_bp.route("/search")
def search_view():
    query = (request.args.get("q") or "").strip()
    tab = (request.args.get("tab") or "scholarships").strip().lower()
    if tab not in ("scholarships", "research", "universities", "programmes"):
        tab = "scholarships"

    return render_template(
        "search_extra.html",
        query=query,
        active_tab=tab,
        availability=source_availability(),
    )


def _empty():
    return jsonify({"query": "", "results": [], "total": 0})


@extra_bp.route("/api/scholarships")
def api_scholarships():
    query = (request.args.get("q") or "").strip()
    if not query:
        return _empty()
    results = search_scholarships(query, limit=25)
    return jsonify({
        "query": query,
        "results": results,
        "total": len(results),
        "available": source_availability()["scholarships"],
    })


@extra_bp.route("/api/research")
def api_research():
    query = (request.args.get("q") or "").strip()
    if not query:
        return _empty()
    results = search_research(query, limit=25)
    return jsonify({
        "query": query,
        "results": results,
        "total": len(results),
        "available": source_availability()["research"],
    })


@extra_bp.route("/api/universities")
def api_universities():
    query = (request.args.get("q") or "").strip()
    if not query:
        return _empty()
    results = search_universities(query, limit=25)
    return jsonify({
        "query": query,
        "results": results,
        "total": len(results),
        "available": source_availability()["universities"],
    })


@extra_bp.route("/api/programmes")
def api_programmes():
    query = (request.args.get("q") or "").strip()
    if not query:
        return _empty()
    results = search_programmes(query, limit=25)
    return jsonify({
        "query": query,
        "results": results,
        "total": len(results),
        "available": source_availability()["programmes"],
    })
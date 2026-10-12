"""
Apify sources routes — separate page, separate integration.

Endpoints:
  GET  /apify/                      — renders the lookup page
  POST /apify/api/courses           — lookup a course catalog URL
  POST /apify/api/professors        — lookup a Rate My Professors URL
"""

from flask import Blueprint, jsonify, render_template, request

from services.apify_sources_service import (
    is_apify_available,
    lookup_course_catalog,
    lookup_professors,
)


apify_bp = Blueprint("apify_sources", __name__, url_prefix="/apify")


@apify_bp.route("/")
def index():
    """Render the Apify lookup page."""
    return render_template(
        "apify_sources.html",
        apify_available=is_apify_available(),
    )


@apify_bp.route("/api/courses", methods=["POST"])
def api_courses():
    data = request.get_json(silent=True) or {}
    catalog_url = (data.get("url") or "").strip()
    max_courses = data.get("max_courses", 50)

    if not catalog_url:
        return jsonify({"error": "Please provide a course catalog URL.", "results": []}), 400

    results, err = lookup_course_catalog(catalog_url, max_courses)
    if err:
        return jsonify({"error": err, "results": []}), 400

    return jsonify({
        "results": results,
        "total": len(results),
        "url": catalog_url,
    })


@apify_bp.route("/api/professors", methods=["POST"])
def api_professors():
    data = request.get_json(silent=True) or {}
    search_url = (data.get("url") or "").strip()
    max_items = data.get("max_items", 25)

    if not search_url:
        return jsonify({"error": "Please provide a Rate My Professors URL.", "results": []}), 400

    results, err = lookup_professors(search_url, max_items)
    if err:
        return jsonify({"error": err, "results": []}), 400

    return jsonify({
        "results": results,
        "total": len(results),
        "url": search_url,
    })
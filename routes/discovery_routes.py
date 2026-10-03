"""
Routes for the shared discovery catalog.

POST /discoveries/save     - record a search result into the catalog
GET  /discoveries/lookup   - is a URL already in the catalog?
GET  /discoveries/search   - search the catalog
"""

from flask import Blueprint, jsonify, request

from services.discovery_service import (
    is_discovered,
    record_discovery,
    search_discoveries,
)


discovery_bp = Blueprint("discoveries", __name__, url_prefix="/discoveries")


@discovery_bp.route("/save", methods=["POST"])
def save_view():
    """Accepts JSON. No login required — the catalog is public."""
    payload = request.get_json(silent=True) or {}

    url = (payload.get("url") or "").strip()
    title = (payload.get("title") or "").strip()

    if not url or not title:
        return jsonify({
            "error": "missing_fields",
            "message": "url and title are required",
        }), 400

    saved_by = None
    try:
        from flask import session
        saved_by = session.get("user_id")
    except Exception:
        pass

    try:
        row = record_discovery(payload, saved_by=saved_by)
    except Exception as exc:
        return jsonify({
            "error": "save_failed",
            "message": str(exc)[:200],
        }), 500

    return jsonify({
        "status": "saved",
        "id": row.get("id"),
        "saved_count": row.get("saved_count", 1),
    })


@discovery_bp.route("/lookup", methods=["GET"])
def lookup_view():
    """GET /discoveries/lookup?url=... -> {discovered: bool}"""
    url = (request.args.get("url") or "").strip()
    return jsonify({"discovered": is_discovered(url)})


@discovery_bp.route("/search", methods=["GET"])
def search_view():
    """GET /discoveries/search?q=... -> JSON list."""
    q = (request.args.get("q") or "").strip()
    try:
        limit = min(max(1, int(request.args.get("limit") or 20)), 100)
    except (TypeError, ValueError):
        limit = 20
    return jsonify({"results": search_discoveries(q, limit=limit)})
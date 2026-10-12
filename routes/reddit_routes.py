"""
Reddit search route — page 2 of search results.
"""

from flask import Blueprint, jsonify, render_template, request

from services.reddit_service import is_reddit_available, search_reddit


reddit_bp = Blueprint("reddit", __name__, url_prefix="/reddit")


@reddit_bp.route("/search")
def search_view():
    """Render the Reddit results page."""
    query = (request.args.get("q") or "").strip()
    return render_template(
        "search_reddit.html",
        query=query,
        reddit_available=is_reddit_available(),
    )


@reddit_bp.route("/api/search")
def api_search():
    """Return Reddit results as JSON for the page's JS."""
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"query": "", "results": [], "total": 0})

    results = search_reddit(query, limit=25)
    return jsonify({
        "query": query,
        "results": results,
        "total": len(results),
        "available": is_reddit_available(),
    })
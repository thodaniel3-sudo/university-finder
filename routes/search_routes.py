"""
Free-text search across our database and (optionally) the web.
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.search_service import search_everything
from services.supabase_service import get_public_client

search_bp = Blueprint("search", __name__)


@search_bp.route("/search")
def search_view():
    query = (request.args.get("q") or "").strip()
    results = search_everything(query)

    # TEMPORARY DEBUG — remove after fixing
    import sys
    print(
        f"[DEBUG SEARCH] query={query!r} "
        f"db_count={results.get('db_count')} "
        f"web_available={results.get('web_available')} "
        f"web_results={len(results.get('web_results') or [])}",
        file=sys.stderr,
    )

    return render_template(
        "search.html",
        query=query,
        results=results,
    )

@search_bp.route("/request-programme", methods=["POST"])
def request_programme():
    """
    User-submitted request for a programme we don't have.

    Works for both logged-in users and guests. If the user is logged in,
    we link the request to their user_id. Otherwise, we just record the
    query.
    """
    query = (request.form.get("query") or "").strip()
    contact_email = (request.form.get("contact_email") or "").strip()
    notes = (request.form.get("notes") or "").strip()

    if not query:
        flash("Please describe the programme you're looking for.", "warning")
        return redirect(url_for("search.search_view"))

    payload = {
        "user_id": session.get("user_id"),  # may be None for guests
        "contact_email": contact_email or None,
        "requested_query": query[:500],
        "notes": notes[:2000] or None,
        "status": "pending",
    }

    try:
        client = get_public_client()
        client.table("programme_requests").insert(payload).execute()
        flash(
            "Thank you. We've logged your request and will look into it.",
            "success",
        )
    except Exception as exc:
        flash(f"Could not submit request: {exc}", "danger")

    # Send the user back to their search results.
    return redirect(url_for("search.search_view", q=query))
"""
Sitemap route.

Exposes /sitemap.xml as a dynamic endpoint that lists every public page:
homepage, about, universities index, and every university and programme
detail page.

Private pages (dashboard, profile, applications, emails, etc.) are
intentionally excluded so they never enter search engines.
"""

from flask import Blueprint, Response, render_template

from services.supabase_service import get_public_client


sitemap_bp = Blueprint("sitemap", __name__)


def _fetch_universities() -> list[dict]:
    """Return every active university as {id: int}."""
    try:
        client = get_public_client()
        response = (
            client.table("universities")
            .select("id")
            .eq("status", "active")
            .execute()
        )
        return response.data or []
    except Exception as exc:
        print(f"[sitemap] universities fetch failed: {exc}")
        return []


def _fetch_programmes() -> list[dict]:
    """Return every active programme as {id: int}."""
    try:
        client = get_public_client()
        response = (
            client.table("programmes")
            .select("id")
            .eq("status", "active")
            .execute()
        )
        return response.data or []
    except Exception as exc:
        print(f"[sitemap] programmes fetch failed: {exc}")
        return []


@sitemap_bp.route("/sitemap.xml")
def sitemap():
    """Return the XML sitemap."""
    universities = _fetch_universities()
    programmes = _fetch_programmes()

    xml = render_template(
        "sitemap.xml",
        universities=universities,
        programmes=programmes,
    )

    return Response(
        xml,
        mimetype="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )

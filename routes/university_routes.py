"""
Public university browse and detail routes.
No login required.
"""

from flask import Blueprint, abort, render_template, request

from services.university_service import (
    count_universities,
    get_university,
    list_universities,
)

university_bp = Blueprint("universities", __name__)

PAGE_SIZE = 10


@university_bp.route("/universities")
def list_view():
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    offset = (page - 1) * PAGE_SIZE
    rows = list_universities(limit=PAGE_SIZE, offset=offset)
    total = count_universities()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    return render_template(
        "universities.html",
        universities=rows,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@university_bp.route("/universities/<int:university_id>")
def detail_view(university_id: int):
    uni = get_university(university_id)
    if uni is None:
        abort(404)
    return render_template("university.html", university=uni)
"""
Document upload, list, download, delete.
"""

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from services.auth_decorators import current_user, login_required
from services.document_service import (
    DocumentError,
    count_by_type,
    delete_document,
    get_document,
    get_download_url,
    list_documents,
    upload_document,
)
from services.forms import DOCUMENT_TYPES, DocumentUploadForm

document_bp = Blueprint("documents", __name__)

TYPE_LABELS = dict(DOCUMENT_TYPES)


@document_bp.route("/documents", methods=["GET", "POST"])
@login_required
def list_view():
    user = current_user()
    form = DocumentUploadForm()

    if form.validate_on_submit():
        try:
            upload_document(
                user_id=user["id"],
                access_token=user["access_token"],
                file_storage=form.file.data,
                document_type=form.document_type.data,
                display_name=(form.display_name.data or "").strip(),
            )
        except DocumentError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("documents.list_view"))

        flash("Document uploaded.", "success")
        return redirect(url_for("documents.list_view"))

    try:
        docs = list_documents(user["id"], user["access_token"])
    except Exception:
        docs = []

    try:
        type_counts = count_by_type(user["id"], user["access_token"])
    except Exception:
        type_counts = {}

    return render_template(
        "documents.html",
        documents=docs,
        type_labels=TYPE_LABELS,
        type_counts=type_counts,
        form=form,
    )


@document_bp.route("/documents/<int:document_id>/download")
@login_required
def download_view(document_id: int):
    user = current_user()
    doc = get_document(user["id"], user["access_token"], document_id)
    if doc is None:
        abort(404)

    try:
        url = get_download_url(user["access_token"], doc["storage_path"])
    except DocumentError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("documents.list_view"))

    # Redirect the browser straight at the signed Storage URL.
    return redirect(url)


@document_bp.route("/documents/<int:document_id>/delete", methods=["POST"])
@login_required
def delete_view(document_id: int):
    user = current_user()
    try:
        delete_document(user["id"], user["access_token"], document_id)
        flash("Document deleted.", "info")
    except DocumentError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("documents.list_view"))
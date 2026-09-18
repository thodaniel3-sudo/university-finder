"""
Document upload, list, download, delete.

Files go to Supabase Storage at path "<user_id>/<uuid>.<ext>".
Metadata goes to the public.documents table.

Every call uses the USER client, so RLS + Storage policies enforce
ownership. We never use the admin client for user files.
"""

import uuid
from pathlib import Path

from werkzeug.utils import secure_filename

from services.supabase_service import get_user_client


BUCKET = "documents"

# Allowed extensions and their MIME types. Kept deliberately small.
ALLOWED_TYPES: dict[str, str] = {
    ".pdf":  "application/pdf",
    ".doc":  "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
}

MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class DocumentError(Exception):
    """User-facing error from document operations."""


# ============================================================
# Validation
# ============================================================

def validate_upload(file_storage) -> tuple[str, str]:
    """
    Validate an uploaded file.

    Returns (safe_display_name, extension) on success.
    Raises DocumentError with a user-facing message on failure.
    """
    if not file_storage or not file_storage.filename:
        raise DocumentError("Please choose a file.")

    original = file_storage.filename
    ext = Path(original).suffix.lower()

    if ext not in ALLOWED_TYPES:
        allowed_list = ", ".join(sorted(ALLOWED_TYPES.keys()))
        raise DocumentError(
            f"File type '{ext}' is not allowed. Allowed types: {allowed_list}."
        )

    # Size check: seek to end of stream, then rewind.
    file_storage.stream.seek(0, 2)  # SEEK_END
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)  # SEEK_SET

    if size == 0:
        raise DocumentError("The file is empty.")
    if size > MAX_SIZE_BYTES:
        raise DocumentError(
            f"File is too large ({size // 1024} KB). "
            f"Maximum is {MAX_SIZE_BYTES // (1024 * 1024)} MB."
        )

    return original, ext


# ============================================================
# Operations
# ============================================================

def upload_document(
    user_id: str,
    access_token: str,
    file_storage,
    document_type: str,
    display_name: str,
) -> dict:
    """
    Upload one file and insert its metadata.

    Returns the created metadata row.
    """
    original_name, ext = validate_upload(file_storage)

    # A random storage filename avoids collisions and hides the original name.
    storage_filename = f"{uuid.uuid4().hex}{ext}"
    storage_path = f"{user_id}/{storage_filename}"

    # Read file bytes into memory. Fine for files up to 5 MB.
    data = file_storage.stream.read()

    client = get_user_client(access_token)

    try:
        client.storage.from_(BUCKET).upload(
            path=storage_path,
            file=data,
            file_options={
                "content-type": ALLOWED_TYPES[ext],
                "upsert": "false",
            },
        )
    except Exception as exc:
        raise DocumentError(f"Upload failed: {exc}") from exc

    # Insert metadata. If this fails, try to remove the orphaned file.
    try:
        response = (
            client.table("documents")
            .insert({
                "user_id": user_id,
                "document_type": document_type,
                "display_name": display_name or original_name,
                "file_name": secure_filename(original_name),
                "storage_path": storage_path,
                "content_type": ALLOWED_TYPES[ext],
                "size_bytes": len(data),
            })
            .execute()
        )
    except Exception as exc:
        # Best-effort cleanup — don't mask the original error if it fails.
        try:
            client.storage.from_(BUCKET).remove([storage_path])
        except Exception:
            pass
        raise DocumentError(f"Could not save document metadata: {exc}") from exc

    return response.data[0] if response.data else {}


def list_documents(user_id: str, access_token: str) -> list[dict]:
    """Return the user's documents, newest first."""
    client = get_user_client(access_token)
    response = (
        client.table("documents")
        .select("*")
        .eq("user_id", user_id)
        .order("uploaded_at", desc=True)
        .execute()
    )
    return response.data or []


def get_document(user_id: str, access_token: str, document_id: int) -> dict | None:
    client = get_user_client(access_token)
    response = (
        client.table("documents")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", document_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


def get_download_url(access_token: str, storage_path: str, expires_in: int = 300) -> str:
    """
    Generate a short-lived signed URL for downloading one file.

    `expires_in` is seconds. 300 = 5 minutes. Enough for a download click.
    """
    client = get_user_client(access_token)
    response = client.storage.from_(BUCKET).create_signed_url(
        storage_path, expires_in
    )
    # SDK returns {'signedURL': 'https://...'} or {'signedUrl': ...} depending on version.
    url = response.get("signedURL") or response.get("signedUrl") or response.get("signed_url")
    if not url:
        raise DocumentError("Could not generate a download link.")
    return url


def delete_document(user_id: str, access_token: str, document_id: int) -> None:
    """Remove the storage object and the metadata row."""
    doc = get_document(user_id, access_token, document_id)
    if doc is None:
        raise DocumentError("Document not found.")

    client = get_user_client(access_token)

    # Try Storage first. If the object is already gone, proceed to delete metadata.
    try:
        client.storage.from_(BUCKET).remove([doc["storage_path"]])
    except Exception:
        pass

    client.table("documents").delete().eq("user_id", user_id).eq("id", document_id).execute()


def count_by_type(user_id: str, access_token: str) -> dict[str, int]:
    """Return counts per document_type for the UI summary."""
    client = get_user_client(access_token)
    response = (
        client.table("documents")
        .select("document_type")
        .eq("user_id", user_id)
        .execute()
    )
    counts: dict[str, int] = {}
    for row in response.data or []:
        t = row["document_type"]
        counts[t] = counts.get(t, 0) + 1
    return counts
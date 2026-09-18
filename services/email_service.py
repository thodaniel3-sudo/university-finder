"""
Email service — persistence layer.

Phase 15 provides draft/save/list/delete operations.
Phase 16 will add `send()` which calls the provider (or the mailto handoff).
"""

from typing import Any

from services.supabase_service import get_user_client


ALLOWED_UPDATE_FIELDS = {
    "recipient_email",
    "reply_to",
    "subject",
    "body",
    "email_type",
    "attachment_paths",
    "status",
}


def create_draft(
    user_id: str,
    access_token: str,
    *,
    recipient_email: str,
    subject: str,
    body: str,
    email_type: str,
    reply_to: str | None = None,
    university_id: int | None = None,
    programme_id: int | None = None,
    attachment_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Insert a new email log row with status='draft'."""
    client = get_user_client(access_token)
    payload = {
        "user_id": user_id,
        "recipient_email": recipient_email,
        "reply_to": reply_to,
        "subject": subject,
        "body": body,
        "email_type": email_type,
        "status": "draft",
        "university_id": university_id,
        "programme_id": programme_id,
        "attachment_paths": attachment_paths or [],
    }
    response = client.table("email_logs").insert(payload).execute()
    return response.data[0] if response.data else {}


def update_draft(
    user_id: str,
    access_token: str,
    email_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Update whitelisted fields on an email log row."""
    clean = {k: v for k, v in payload.items() if k in ALLOWED_UPDATE_FIELDS}
    client = get_user_client(access_token)
    response = (
        client.table("email_logs")
        .update(clean)
        .eq("user_id", user_id)
        .eq("id", email_id)
        .execute()
    )
    return response.data[0] if response.data else {}


def get_email(user_id: str, access_token: str, email_id: int) -> dict[str, Any] | None:
    client = get_user_client(access_token)
    response = (
        client.table("email_logs")
        .select(
            "*, "
            "universities(id, name, country, city, website_url, official_email), "
            "programmes(id, programme_name, degree_level, field, programme_url)"
        )
        .eq("user_id", user_id)
        .eq("id", email_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


def list_emails(user_id: str, access_token: str) -> list[dict[str, Any]]:
    """Return all email log rows for a user, newest first."""
    client = get_user_client(access_token)
    response = (
        client.table("email_logs")
        .select(
            "id, status, email_type, recipient_email, subject, "
            "sent_at, created_at, updated_at, error_message, "
            "universities(id, name, country), "
            "programmes(id, programme_name, degree_level)"
        )
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def delete_email(user_id: str, access_token: str, email_id: int) -> None:
    client = get_user_client(access_token)
    client.table("email_logs").delete().eq("user_id", user_id).eq("id", email_id).execute()


def count_by_status(user_id: str, access_token: str) -> dict[str, int]:
    client = get_user_client(access_token)
    response = (
        client.table("email_logs")
        .select("status")
        .eq("user_id", user_id)
        .execute()
    )
    counts: dict[str, int] = {}
    for row in response.data or []:
        s = row["status"]
        counts[s] = counts.get(s, 0) + 1
    return counts


def mark_handed_off(user_id: str, access_token: str, email_id: int) -> dict[str, Any]:
    """Mark an email as handed off to the user's email client (Phase 16)."""
    client = get_user_client(access_token)
    response = (
        client.table("email_logs")
        .update({"status": "handed_off"})
        .eq("user_id", user_id)
        .eq("id", email_id)
        .execute()
    )
    return response.data[0] if response.data else {}


def mark_sent(user_id: str, access_token: str, email_id: int) -> dict[str, Any]:
    """Mark an email as confirmed-sent by the user (Phase 16)."""
    from datetime import datetime, timezone
    client = get_user_client(access_token)
    response = (
        client.table("email_logs")
        .update({
            "status": "sent",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("user_id", user_id)
        .eq("id", email_id)
        .execute()
    )
    return response.data[0] if response.data else {}
"""
Build handoff URLs for sending an email through the user's own email client.

This module is PURE — no database, no Flask. Takes strings in, returns strings out.

Two handoff mechanisms:

1. `mailto:` URL — opens the OS default email client (Outlook, Apple Mail,
   Gmail app on mobile, etc.) with recipient/subject/body pre-filled.
   Universally supported. The student sends from whatever account their
   client is configured for.

2. Gmail web compose URL — opens Gmail's web composer in a new tab. Only
   works if the user is logged into Gmail in that browser. Useful for users
   who don't have a desktop mail client.

Both are preview links. The actual send happens when the user clicks Send
inside their email client.
"""

from urllib.parse import quote, urlencode


def build_mailto_url(
    recipient: str,
    subject: str,
    body: str,
    cc: str | None = None,
) -> str:
    """
    Build a mailto: URL that opens the user's default email client.

    Uses `quote` to percent-encode each component. The `mailto:` scheme
    accepts a small subset of URI-encoded characters; we stay conservative
    and encode everything except the safest ones.
    """
    # `quote` with safe="" percent-encodes everything except letters/digits.
    # We allow spaces to become %20 (browsers accept either + or %20 in mailto).
    encoded_subject = quote(subject, safe="")
    encoded_body = quote(body, safe="")

    parts = [f"mailto:{recipient}"]
    query_parts = []
    if subject:
        query_parts.append(f"subject={encoded_subject}")
    if body:
        query_parts.append(f"body={encoded_body}")
    if cc:
        query_parts.append(f"cc={quote(cc, safe='')}")

    if query_parts:
        parts.append("?" + "&".join(query_parts))

    return "".join(parts)


def build_gmail_compose_url(
    recipient: str,
    subject: str,
    body: str,
) -> str:
    """
    Build a URL that opens Gmail's web composer in a new tab.

    Only works for users logged into Gmail in the current browser.
    Falls back silently to a Gmail login page if the user isn't logged in.
    """
    params = {
        "view": "cm",   # compose mode
        "fs":   "1",    # full-screen
        "to":   recipient,
        "su":   subject,
        "body": body,
    }
    return "https://mail.google.com/mail/?" + urlencode(params, quote_via=quote)


def is_mailto_safe(url: str) -> bool:
    """
    Sanity check: ensure a mailto URL isn't going to be silently rejected
    by the browser due to length. Most browsers cap around 2000 chars;
    some older ones cap lower. We warn over 1800.
    """
    return len(url) <= 1800
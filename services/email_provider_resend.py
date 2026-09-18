"""
Dormant Resend integration.

This module is intentionally NOT imported by any route today.
It exists so that when you buy a domain and set EMAIL_API_KEY,
the activation is a one-line change.

To activate (later):
  1. Sign up at resend.com
  2. Verify a domain you own (add DNS records they provide)
  3. Set these in .env:
       EMAIL_API_KEY=re_xxxxxxxxxxxxx
       EMAIL_FROM=inquiries@yourdomain.com
  4. In templates/email_send.html, show a "Send via University Finder"
     button when `config['EMAIL_API_KEY']` is truthy.
  5. In email_routes.py, add a route that calls send_via_resend().

Until then, this file is inert — no imports, no calls.
"""

from typing import Any

from flask import current_app


class ResendNotConfigured(RuntimeError):
    """Raised if Resend is called before EMAIL_API_KEY is set."""


def is_resend_configured() -> bool:
    """True if EMAIL_API_KEY is set in config."""
    return bool(current_app.config.get("EMAIL_API_KEY"))


def send_via_resend(
    *,
    to: str,
    subject: str,
    body: str,
    reply_to: str | None = None,
) -> dict[str, Any]:
    """
    Send one email via Resend.

    Requires `EMAIL_API_KEY` and `EMAIL_FROM` to be set.
    Raises ResendNotConfigured if either is missing.

    Never call this without user confirmation in the UI.
    """
    if not is_resend_configured():
        raise ResendNotConfigured(
            "Resend is not configured. Set EMAIL_API_KEY and EMAIL_FROM in .env."
        )

    api_key = current_app.config["EMAIL_API_KEY"]
    sender = current_app.config.get("EMAIL_FROM") or "onboarding@resend.dev"

    # Import here so the module stays importable even without resend installed.
    try:
        import resend
    except ImportError as exc:
        raise ResendNotConfigured(
            "The 'resend' package is not installed. "
            "Run: python -m pip install resend"
        ) from exc

    resend.api_key = api_key

    params = {
        "from": sender,
        "to": [to],
        "subject": subject,
        "text": body,
    }
    if reply_to:
        params["reply_to"] = reply_to

    try:
        response = resend.Emails.send(params)
    except Exception as exc:
        raise RuntimeError(f"Resend send failed: {exc}") from exc

    return response if isinstance(response, dict) else {"id": str(response)}
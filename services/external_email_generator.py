"""
Generate a polite draft email for a web-discovered programme.

This is a simpler generator than services/email_generator.py:
we know the programme title from the search result, but we don't
have a university record. So the draft is minimal and uses the
title directly.
"""

from textwrap import dedent


def generate_external_draft(profile: dict | None, external: dict) -> dict:
    """
    Return {"subject": str, "body": str}.
    """
    profile = profile or {}

    full_name = (profile.get("full_name") or "[your name]").strip()
    country = (profile.get("country") or "").strip()
    title = (external.get("title") or "the programme").strip()
    domain = (external.get("source_domain") or "the university").strip()

    signature_lines = [full_name]
    if country:
        signature_lines.append(country)
    signature = "\n".join(signature_lines)

    subject = f"Inquiry about {title}"

    body = dedent(f"""\
    Dear Sir/Madam,

    My name is {full_name}, and I am writing from {country or '[your country]'}.

    I am interested in {title}, which I found via {domain}. I would like
    to confirm a few details about the programme, including:
      - Admission requirements and any prerequisite degrees
      - The application deadline for the next intake
      - Tuition fees for international applicants
      - Any documents required from international applicants

    I would be grateful for any information you can provide.

    Thank you for your time.

    Kind regards,
    {signature}
    """).strip()

    return {"subject": subject, "body": body}
"""
Generate draft inquiry emails from templates + user profile + programme data.

This module is PURE — no database, no Flask, no side effects.
Takes dicts in, returns a dict with subject + body.

The generated text is intentionally modest, respectful, and free of
sales language. A student should be able to send it as-is.
"""

from textwrap import dedent


def _first_name(full_name: str | None) -> str:
    if not full_name:
        return "there"
    return full_name.strip().split()[0]


def _signature(profile: dict) -> str:
    """Standard closing block for every email."""
    name = (profile.get("full_name") or "[your name]").strip()
    country = (profile.get("country") or "").strip()
    lines = [name]
    if country:
        lines.append(country)
    return "\n".join(lines)


def _programme_line(programme: dict | None) -> str:
    if not programme:
        return "your institution"
    name = programme.get("programme_name") or "the programme"
    level = programme.get("degree_level") or ""
    return f"the {level} {name}".strip()


def _salutation(university: dict, programme: dict | None) -> str:
    """Opening line of the email."""
    if programme:
        return f"Dear {university.get('name', 'Sir/Madam')} Admissions Team,"
    return f"Dear {university.get('name', 'Sir/Madam')} Team,"


def generate_email_draft(
    profile: dict,
    university: dict,
    programme: dict | None,
    purpose: str,
) -> dict:
    """
    Return {"subject": str, "body": str} for the given purpose.

    The body is plain text (no HTML). The user can edit both fields
    before saving or sending.
    """
    uni_name = university.get("name") or "the university"
    prog_display = _programme_line(programme)
    salutation = _salutation(university, programme)
    signature = _signature(profile)

    # ---------------- Subject ----------------
    if purpose == "general_inquiry":
        subject = f"Inquiry about programmes at {uni_name}"
    elif purpose == "programme_question":
        subject = f"Question about {prog_display} at {uni_name}"
    elif purpose == "deadline_question":
        subject = f"Application deadline for {prog_display}"
    elif purpose == "fee_question":
        subject = f"Tuition and application fees for {prog_display}"
    elif purpose == "documents_question":
        subject = f"Required documents for {prog_display}"
    elif purpose == "application_followup":
        subject = f"Follow-up: my application to {prog_display}"
    else:  # custom
        subject = "Inquiry from a prospective student"

    # ---------------- Body ----------------
    name_first = _first_name(profile.get("full_name"))
    desired_field = (profile.get("desired_field") or "").strip()
    previous_degree = (profile.get("previous_degree") or "").strip()

    common_open = (
        f"My name is {profile.get('full_name') or '[your name]'}, "
        f"and I am writing from {profile.get('country') or '[your country]'}."
    )

    if purpose == "general_inquiry":
        body = f"""\
{salutation}

{common_open}

I am interested in learning more about the programmes your institution
offers{" in " + desired_field if desired_field else ""}. Could you kindly
share information about available programmes, admission requirements,
and application deadlines for prospective international students?

Thank you for your time.

Kind regards,
{signature}
"""

    elif purpose == "programme_question":
        body = f"""\
{salutation}

{common_open}

I am interested in {prog_display}. I would like to confirm a few details
about the programme, including:
  - Admission requirements and any prerequisite degrees
  - The application deadline for the next intake
  - Whether the programme is offered full-time, part-time, or online
  - Any additional documents required for international applicants

I would be grateful for any information you can provide.

Thank you for your time.

Kind regards,
{signature}
"""

    elif purpose == "deadline_question":
        body = f"""\
{salutation}

{common_open}

I am preparing to apply for {prog_display}. Could you please confirm:
  - The application deadline for the next intake
  - Whether there are multiple intakes per year
  - Any earlier deadlines for international applicants or scholarship consideration

Thank you very much.

Kind regards,
{signature}
"""

    elif purpose == "fee_question":
        body = f"""\
{salutation}

{common_open}

I am considering applying for {prog_display}. I would appreciate
clarification on the following:
  - The application fee (if any) for international applicants
  - The tuition fees for the programme
  - Whether there are scholarships or fee waivers available

Thank you for your help.

Kind regards,
{signature}
"""

    elif purpose == "documents_question":
        body = f"""\
{salutation}

{common_open}

I am preparing my application for {prog_display}. Could you please
confirm the list of documents required from international applicants?
In particular:
  - Whether certified copies of transcripts are required, or if
    scanned uploads are accepted
  - Whether degree certificates need to be translated or evaluated
  - Whether English proficiency test scores are required
  - Any other documents specific to the programme

Thank you for your time.

Kind regards,
{signature}
"""

    elif purpose == "application_followup":
        body = f"""\
{salutation}

{common_open}

I recently submitted my application for {prog_display} and would like
to confirm that it was received. Could you please let me know:
  - Whether my application is complete
  - Whether any additional documents are required
  - An approximate timeline for a decision

Thank you very much.

Kind regards,
{signature}
"""

    else:  # custom — a clean draft the user fills in
        body = f"""\
{salutation}

{common_open}

[Your message here]

Thank you for your time.

Kind regards,
{signature}
"""

    return {
        "subject": subject,
        "body": dedent(body).strip() + "\n",
    }
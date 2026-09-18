"""
Single source of truth for application statuses.

Both the DB check constraint (Phase 13 SQL) and the UI must agree.
This module is what the UI reads.
"""

# Order matters — the UI groups by these in this order.
APPLICATION_STATUSES = [
    ("not_started",                    "Not Started",                    "secondary"),
    ("planning",                       "Planning",                       "info"),
    ("preparing_documents",            "Preparing Documents",            "info"),
    ("ready_to_apply",                 "Ready to Apply",                 "primary"),
    ("applied",                        "Applied",                        "primary"),
    ("under_review",                   "Under Review",                   "warning"),
    ("interview",                      "Interview",                      "warning"),
    ("additional_documents_requested", "Additional Documents Requested", "warning"),
    ("accepted",                       "Accepted",                       "success"),
    ("rejected",                       "Rejected",                       "danger"),
    ("withdrawn",                      "Withdrawn",                      "secondary"),
]

# Fast lookup: code -> label
STATUS_LABELS = {code: label for code, label, _ in APPLICATION_STATUSES}

# Fast lookup: code -> bootstrap color
STATUS_COLORS = {code: color for code, _, color in APPLICATION_STATUSES}

# For WTForms SelectField: choices = [(code, label), ...]
STATUS_CHOICES = [(code, label) for code, label, _ in APPLICATION_STATUSES]


def is_terminal(status_code: str) -> bool:
    """A terminal status ends the process — no further action expected."""
    return status_code in {"accepted", "rejected", "withdrawn"}
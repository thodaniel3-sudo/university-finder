"""
Single source of truth for email purposes (types).

The database CHECK constraint, the form SelectField, and the template
all read from this list.
"""

EMAIL_PURPOSES = [
    ("general_inquiry",     "General inquiry about the university"),
    ("programme_question",  "Question about a specific programme"),
    ("deadline_question",   "Question about application deadlines"),
    ("fee_question",        "Question about tuition or application fees"),
    ("documents_question",  "Question about required documents"),
    ("application_followup","Follow-up on an existing application"),
    ("custom",              "Custom (start from a blank message)"),
]

PURPOSE_LABELS = {code: label for code, label in EMAIL_PURPOSES}
PURPOSE_CHOICES = [(code, label) for code, label in EMAIL_PURPOSES]
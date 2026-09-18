"""
WTForms form definitions.
Flask-WTF handles CSRF tokens automatically when a form
is rendered inside a template using {{ form.hidden_tag() }}.
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    NumberRange,
    Optional,
)

from services.application_statuses import STATUS_CHOICES as APPLICATION_STATUSES_CHOICES
from services.email_purposes import PURPOSE_CHOICES


# ============================================================
# Shared choice constants
# ============================================================

DEGREE_LEVELS = [
    ("", "-- select --"),
    ("Bachelor", "Bachelor's degree"),
    ("Master", "Master's degree"),
    ("PhD", "Doctorate (PhD)"),
    ("Diploma", "Diploma"),
    ("Certificate", "Certificate"),
]

COUNTRIES = [
    ("", "-- select --"),
    ("Nigeria", "Nigeria"),
    ("Ghana", "Ghana"),
    ("Kenya", "Kenya"),
    ("South Africa", "South Africa"),
    ("United Kingdom", "United Kingdom"),
    ("United States", "United States"),
    ("Canada", "Canada"),
    ("Germany", "Germany"),
    ("France", "France"),
    ("Netherlands", "Netherlands"),
    ("Ireland", "Ireland"),
    ("Australia", "Australia"),
    ("Other", "Other"),
]

ENGLISH_LEVELS = [
    ("", "-- select --"),
    ("Native", "Native speaker"),
    ("Fluent", "Fluent (C1/C2)"),
    ("Advanced", "Advanced (B2)"),
    ("Intermediate", "Intermediate (B1)"),
    ("Basic", "Basic (A1/A2)"),
]


# ============================================================
# Auth forms
# ============================================================

class RegisterForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Please enter a valid email address."),
            Length(max=254, message="Email is too long."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, max=72,
                   message="Password must be between 8 and 72 characters."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords do not match."),
        ],
    )
    accept_terms = BooleanField(
        "I understand this platform does not guarantee admission",
        validators=[DataRequired(message="You must acknowledge this to continue.")],
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Please enter a valid email address."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password is required.")],
    )
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Log in")


# ============================================================
# Student profile form
# ============================================================

class ProfileForm(FlaskForm):
    """Student academic profile."""

    # ----- Identity -----
    full_name = StringField(
        "Full name",
        validators=[DataRequired(), Length(max=120)],
    )
    country = SelectField(
        "Country of origin",
        choices=COUNTRIES,
        validators=[DataRequired()],
    )

    # ----- Study intention -----
    degree_level = SelectField(
        "Degree level you are applying for",
        choices=DEGREE_LEVELS,
        validators=[DataRequired()],
    )
    desired_programme = StringField(
        "Desired programme",
        validators=[Optional(), Length(max=200)],
    )
    desired_field = StringField(
        "Desired field",
        validators=[Optional(), Length(max=200)],
    )

    # ----- Previous education -----
    previous_degree = StringField(
        "Previous degree (e.g. BSc Computer Science)",
        validators=[DataRequired(), Length(max=200)],
    )
    previous_field = StringField(
        "Previous field of study",
        validators=[DataRequired(), Length(max=200)],
    )
    cgpa = DecimalField(
        "CGPA",
        places=2,
        validators=[DataRequired(), NumberRange(min=0, max=10)],
    )
    cgpa_scale = DecimalField(
        "CGPA scale (e.g. 4.00 or 5.00)",
        places=2,
        validators=[DataRequired(), NumberRange(min=1, max=10)],
    )
    graduation_year = IntegerField(
        "Graduation year",
        validators=[DataRequired(), NumberRange(min=1950, max=2100)],
    )

    # ----- English proficiency -----
    english_proficiency = SelectField(
        "English proficiency (self-assessed)",
        choices=ENGLISH_LEVELS,
        validators=[Optional()],
    )
    ielts_score = DecimalField(
        "IELTS overall score (optional)",
        places=1,
        validators=[Optional(), NumberRange(min=0, max=9)],
    )
    toefl_score = IntegerField(
        "TOEFL overall score (optional)",
        validators=[Optional(), NumberRange(min=0, max=120)],
    )

    other_info = TextAreaField(
        "Other academic information (optional)",
        validators=[Optional(), Length(max=2000)],
    )

    submit = SubmitField("Save profile")


# ============================================================
# Application tracker form
# ============================================================

class ApplicationForm(FlaskForm):
    """Edit form for a tracked application."""

    status = SelectField(
        "Status",
        choices=APPLICATION_STATUSES_CHOICES,
        validators=[DataRequired()],
    )
    application_date = DateField(
        "Application date (optional)",
        validators=[Optional()],
        format="%Y-%m-%d",
    )
    deadline = DateField(
        "Deadline (optional)",
        validators=[Optional()],
        format="%Y-%m-%d",
    )
    application_url = StringField(
        "Application URL (optional)",
        validators=[Optional(), Length(max=500)],
    )
    notes = TextAreaField(
        "Notes (optional)",
        validators=[Optional(), Length(max=5000)],
    )
    submit = SubmitField("Save application")


# ============================================================
# Document upload form
# ============================================================

DOCUMENT_TYPES = [
    ("cv",                    "CV / Résumé"),
    ("transcript",            "Academic transcript"),
    ("degree_certificate",    "Degree certificate"),
    ("passport",              "Passport / ID"),
    ("english_certificate",   "English test certificate (IELTS/TOEFL)"),
    ("motivation_letter",     "Motivation letter"),
    ("recommendation_letter", "Recommendation letter"),
    ("other",                 "Other"),
]


class DocumentUploadForm(FlaskForm):
    document_type = SelectField(
        "Document type",
        choices=DOCUMENT_TYPES,
        validators=[DataRequired()],
    )
    display_name = StringField(
        "Display name (optional)",
        validators=[Optional(), Length(max=200)],
    )
    file = FileField(
        "File (PDF, DOC, DOCX, JPG, PNG — max 5 MB)",
        validators=[
            FileRequired(message="Please select a file."),
            FileAllowed(
                ["pdf", "doc", "docx", "jpg", "jpeg", "png"],
                message="Only PDF, DOC, DOCX, JPG, and PNG files are allowed.",
            ),
        ],
    )
    submit = SubmitField("Upload")


# ============================================================
# Email forms
# ============================================================

class EmailComposeForm(FlaskForm):
    """Pick purpose + university/programme; generate a draft."""

    email_type = SelectField(
        "Purpose",
        choices=PURPOSE_CHOICES,
        validators=[DataRequired()],
    )
    university_id = SelectField(
        "University",
        coerce=int,
        validators=[DataRequired()],
    )
    programme_id = SelectField(
        "Programme (optional)",
        coerce=int,
        validators=[Optional()],
    )
    submit = SubmitField("Generate draft")


class EmailReviewForm(FlaskForm):
    """Review/edit a generated draft before saving."""

    recipient_email = StringField(
        "To",
        validators=[
            DataRequired(message="Recipient email is required."),
            Email(message="Please enter a valid email address."),
            Length(max=320),
        ],
    )
    subject = StringField(
        "Subject",
        validators=[
            DataRequired(message="Subject is required."),
            Length(max=300),
        ],
    )
    body = TextAreaField(
        "Message",
        validators=[
            DataRequired(message="Message body is required."),
            Length(max=20000),
        ],
    )
    email_type = SelectField(
        "Purpose",
        choices=PURPOSE_CHOICES,
        validators=[DataRequired()],
    )
    save_draft = SubmitField("Save as draft")
    send = SubmitField("Send email")


# ============================================================
# Admin forms
# ============================================================

ADMIN_DEGREE_LEVELS = [
    ("Bachelor", "Bachelor's"),
    ("Master", "Master's"),
    ("PhD", "Doctorate (PhD)"),
    ("Diploma", "Diploma"),
    ("Certificate", "Certificate"),
]

VERIFICATION_STATUSES = [
    ("unverified", "Unverified"),
    ("verified", "Verified"),
    ("unknown", "Unknown"),
    ("requires_verification", "Requires verification"),
    ("outdated", "Outdated"),
]

UNIVERSITY_STATUSES = [
    ("active", "Active"),
    ("inactive", "Inactive"),
    ("pending_verification", "Pending verification"),
]


class AdminUniversityForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=200)])
    country = StringField("Country", validators=[DataRequired(), Length(max=100)])
    state_region = StringField("State / region", validators=[Optional(), Length(max=100)])
    city = StringField("City", validators=[Optional(), Length(max=100)])
    website_url = StringField("Website URL", validators=[Optional(), Length(max=500)])
    official_email = StringField(
        "Official email",
        validators=[Optional(), Email(message="Enter a valid email or leave blank."), Length(max=320)],
    )
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    source_url = StringField("Source URL", validators=[Optional(), Length(max=500)])
    status = SelectField("Status", choices=UNIVERSITY_STATUSES, validators=[DataRequired()])
    submit = SubmitField("Save university")


class AdminProgrammeForm(FlaskForm):
    university_id = SelectField("University", coerce=int, validators=[DataRequired()])
    programme_name = StringField("Programme name", validators=[DataRequired(), Length(max=300)])
    degree_level = SelectField("Degree level", choices=ADMIN_DEGREE_LEVELS, validators=[DataRequired()])
    field = StringField("Field", validators=[Optional(), Length(max=200)])
    specialization = StringField("Specialization", validators=[Optional(), Length(max=200)])
    language = StringField("Language", validators=[Optional(), Length(max=100)])
    study_mode = StringField("Study mode", validators=[Optional(), Length(max=100)])
    duration = StringField("Duration", validators=[Optional(), Length(max=100)])
    programme_url = StringField("Programme URL", validators=[Optional(), Length(max=500)])
    application_url = StringField("Application URL", validators=[Optional(), Length(max=500)])
    status = SelectField("Status", choices=UNIVERSITY_STATUSES, validators=[DataRequired()])
    submit = SubmitField("Save programme")


class AdminRequirementsForm(FlaskForm):
    minimum_cgpa = DecimalField(
        "Minimum CGPA", places=2,
        validators=[Optional(), NumberRange(min=0, max=10)],
    )
    minimum_cgpa_scale = DecimalField(
        "CGPA scale", places=2,
        validators=[Optional(), NumberRange(min=1, max=10)],
    )
    minimum_degree = StringField("Minimum degree", validators=[Optional(), Length(max=200)])
    required_field = StringField("Required field", validators=[Optional(), Length(max=200)])
    english_requirement = StringField("English requirement", validators=[Optional(), Length(max=300)])
    ielts_required = BooleanField("IELTS required")
    ielts_minimum_score = DecimalField(
        "IELTS minimum score", places=1,
        validators=[Optional(), NumberRange(min=0, max=9)],
    )
    toefl_required = BooleanField("TOEFL required")
    toefl_minimum_score = IntegerField(
        "TOEFL minimum score",
        validators=[Optional(), NumberRange(min=0, max=120)],
    )
    gre_required = BooleanField("GRE required")
    work_experience_required = StringField("Work experience required", validators=[Optional(), Length(max=200)])
    other_requirements = TextAreaField("Other requirements", validators=[Optional(), Length(max=2000)])
    source_url = StringField("Source URL", validators=[Optional(), Length(max=500)])
    verification_status = SelectField(
        "Verification status",
        choices=VERIFICATION_STATUSES,
        validators=[DataRequired()],
    )
    submit = SubmitField("Save requirements")
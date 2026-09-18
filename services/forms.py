"""
WTForms form definitions.
Flask-WTF handles CSRF tokens automatically when a form
is rendered inside a template using {{ form.hidden_tag() }}.
"""

from services.application_statuses import STATUS_CHOICES as APPLICATION_STATUSES_CHOICES
from wtforms import DateField
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
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


# ============================================================
# Choice constants for SelectField dropdowns
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
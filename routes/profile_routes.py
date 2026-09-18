"""
Student profile routes.
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    url_for,
)

from services.auth_decorators import current_user, login_required
from services.forms import ProfileForm
from services.profile_service import (
    get_profile,
    profile_completion,
    upsert_profile,
)

profile_bp = Blueprint("profile", __name__)


def _populate_form_from_profile(form: ProfileForm, profile: dict) -> None:
    """Copy values from a profile dict onto a WTForms form."""
    for field_name in (
        "full_name", "country", "degree_level", "desired_programme",
        "desired_field", "previous_degree", "previous_field",
        "cgpa", "cgpa_scale", "graduation_year",
        "english_proficiency", "ielts_score", "toefl_score", "other_info",
    ):
        if hasattr(form, field_name):
            getattr(form, field_name).data = profile.get(field_name)


@profile_bp.route("/profile", methods=["GET", "POST"])
@login_required
def view_profile():
    user = current_user()
    token = user["access_token"]
    existing = get_profile(user["id"], token)

    form = ProfileForm()

    if form.validate_on_submit():
        payload = {
            "full_name": form.full_name.data,
            "country": form.country.data,
            "degree_level": form.degree_level.data,
            "desired_programme": form.desired_programme.data or None,
            "desired_field": form.desired_field.data or None,
            "previous_degree": form.previous_degree.data,
            "previous_field": form.previous_field.data,
            "cgpa": float(form.cgpa.data) if form.cgpa.data is not None else None,
            "cgpa_scale": float(form.cgpa_scale.data) if form.cgpa_scale.data is not None else None,
            "graduation_year": form.graduation_year.data,
            "english_proficiency": form.english_proficiency.data or None,
            "ielts_score": float(form.ielts_score.data) if form.ielts_score.data is not None else None,
            "toefl_score": form.toefl_score.data,
            "other_info": form.other_info.data or None,
        }

        upsert_profile(user["id"], token, payload)
        flash("Profile saved.", "success")
        return redirect(url_for("profile.view_profile"))

    # On GET, pre-fill form from stored profile.
    if existing and not form.is_submitted():
        _populate_form_from_profile(form, existing)

    completion = profile_completion(existing)

    return render_template(
        "profile.html",
        form=form,
        profile=existing,
        completion=completion,
    )
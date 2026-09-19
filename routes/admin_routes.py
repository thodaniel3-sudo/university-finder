"""
Admin dashboard and CRUD routes.
Every route is protected by @admin_required.
"""

import csv
import io

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from services.admin_decorators import admin_required
from services.admin_service import (
    create_programme,
    create_university,
    get_programme,
    get_requirements_for_programme,
    get_university,
    list_all_programmes,
    list_all_universities,
    stats,
    update_programme,
    update_university,
    upsert_requirements,
)
from services.csv_import_service import (
    IMPORT_TYPES,
    ImportError_,
    run_import,
)
from services.forms import (
    AdminProgrammeForm,
    AdminRequirementsForm,
    AdminUniversityForm,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ============================================================
# Dashboard
# ============================================================

@admin_bp.route("/")
@admin_required
def dashboard():
    return render_template("admin/dashboard.html", stats=stats())


# ============================================================
# Universities
# ============================================================

@admin_bp.route("/universities")
@admin_required
def universities_list():
    return render_template(
        "admin/universities.html",
        universities=list_all_universities(),
    )


def _university_payload(form: AdminUniversityForm) -> dict:
    return {
        "name": form.name.data.strip(),
        "country": form.country.data.strip(),
        "state_region": (form.state_region.data or "").strip() or None,
        "city": (form.city.data or "").strip() or None,
        "website_url": (form.website_url.data or "").strip() or None,
        "official_email": (form.official_email.data or "").strip() or None,
        "description": (form.description.data or "").strip() or None,
        "source_url": (form.source_url.data or "").strip() or None,
        "status": form.status.data,
    }


@admin_bp.route("/universities/new", methods=["GET", "POST"])
@admin_required
def universities_new():
    form = AdminUniversityForm()
    if form.validate_on_submit():
        try:
            create_university(_university_payload(form))
            flash("University created.", "success")
            return redirect(url_for("admin.universities_list"))
        except Exception as exc:
            flash(f"Could not create university: {exc}", "danger")
    return render_template("admin/university_form.html", form=form, university=None)


@admin_bp.route("/universities/<int:university_id>/edit", methods=["GET", "POST"])
@admin_required
def universities_edit(university_id: int):
    university = get_university(university_id)
    if university is None:
        abort(404)

    form = AdminUniversityForm(data=university)
    if form.validate_on_submit():
        try:
            update_university(university_id, _university_payload(form))
            flash("University updated.", "success")
            return redirect(url_for("admin.universities_list"))
        except Exception as exc:
            flash(f"Could not update university: {exc}", "danger")
    return render_template("admin/university_form.html", form=form, university=university)


# ============================================================
# Programmes
# ============================================================

@admin_bp.route("/programmes")
@admin_required
def programmes_list():
    return render_template(
        "admin/programmes.html",
        programmes=list_all_programmes(),
    )


def _populate_university_choices(form: AdminProgrammeForm):
    form.university_id.choices = [(u["id"], u["name"]) for u in list_all_universities()]


def _programme_payload(form: AdminProgrammeForm) -> dict:
    return {
        "university_id": form.university_id.data,
        "programme_name": form.programme_name.data.strip(),
        "degree_level": form.degree_level.data,
        "field": (form.field.data or "").strip() or None,
        "specialization": (form.specialization.data or "").strip() or None,
        "language": (form.language.data or "").strip() or None,
        "study_mode": (form.study_mode.data or "").strip() or None,
        "duration": (form.duration.data or "").strip() or None,
        "programme_url": (form.programme_url.data or "").strip() or None,
        "application_url": (form.application_url.data or "").strip() or None,
        "status": form.status.data,
    }


@admin_bp.route("/programmes/new", methods=["GET", "POST"])
@admin_required
def programmes_new():
    form = AdminProgrammeForm()
    _populate_university_choices(form)

    if request.method == "GET":
        preselect = request.args.get("university_id", type=int)
        if preselect:
            form.university_id.data = preselect

    if form.validate_on_submit():
        try:
            new_prog = create_programme(_programme_payload(form))
            flash("Programme created. Now add its admission requirements.", "success")
            return redirect(url_for("admin.requirements_edit",
                                    programme_id=new_prog["id"]))
        except Exception as exc:
            flash(f"Could not create programme: {exc}", "danger")

    return render_template("admin/programme_form.html", form=form, programme=None)


@admin_bp.route("/programmes/<int:programme_id>/edit", methods=["GET", "POST"])
@admin_required
def programmes_edit(programme_id: int):
    programme = get_programme(programme_id)
    if programme is None:
        abort(404)

    form = AdminProgrammeForm(data=programme)
    _populate_university_choices(form)

    if form.validate_on_submit():
        try:
            update_programme(programme_id, _programme_payload(form))
            flash("Programme updated.", "success")
            return redirect(url_for("admin.programmes_list"))
        except Exception as exc:
            flash(f"Could not update programme: {exc}", "danger")

    return render_template("admin/programme_form.html", form=form, programme=programme)


# ============================================================
# Requirements
# ============================================================

@admin_bp.route("/programmes/<int:programme_id>/requirements", methods=["GET", "POST"])
@admin_required
def requirements_edit(programme_id: int):
    programme = get_programme(programme_id)
    if programme is None:
        abort(404)

    existing = get_requirements_for_programme(programme_id)
    form = AdminRequirementsForm(data=existing)

    if form.validate_on_submit():
        payload = {
            "minimum_cgpa": float(form.minimum_cgpa.data) if form.minimum_cgpa.data is not None else None,
            "minimum_cgpa_scale": float(form.minimum_cgpa_scale.data) if form.minimum_cgpa_scale.data is not None else None,
            "minimum_degree": (form.minimum_degree.data or "").strip() or None,
            "required_field": (form.required_field.data or "").strip() or None,
            "english_requirement": (form.english_requirement.data or "").strip() or None,
            "ielts_required": form.ielts_required.data,
            "ielts_minimum_score": float(form.ielts_minimum_score.data) if form.ielts_minimum_score.data is not None else None,
            "toefl_required": form.toefl_required.data,
            "toefl_minimum_score": form.toefl_minimum_score.data,
            "gre_required": form.gre_required.data,
            "work_experience_required": (form.work_experience_required.data or "").strip() or None,
            "other_requirements": (form.other_requirements.data or "").strip() or None,
            "source_url": (form.source_url.data or "").strip() or None,
            "verification_status": form.verification_status.data,
        }
        try:
            upsert_requirements(programme_id, payload)
            flash("Requirements saved.", "success")
            return redirect(url_for("admin.programmes_list"))
        except Exception as exc:
            flash(f"Could not save requirements: {exc}", "danger")

    return render_template("admin/requirements_form.html", form=form, programme=programme)


# ============================================================
# Bulk CSV import
# ============================================================

@admin_bp.route("/import", methods=["GET"])
@admin_required
def import_view():
    """The CSV upload page."""
    return render_template(
        "admin/import.html",
        import_types=IMPORT_TYPES,
        results=None,
        selected_type=None,
    )


@admin_bp.route("/import", methods=["POST"])
@admin_required
def import_submit():
    """Handle the CSV upload."""
    import_type = (request.form.get("import_type") or "").strip()
    dry_run = bool(request.form.get("dry_run"))
    uploaded = request.files.get("csv_file")

    if not import_type or import_type not in IMPORT_TYPES:
        flash("Please choose a valid import type.", "danger")
        return redirect(url_for("admin.import_view"))

    if not uploaded or not uploaded.filename:
        flash("Please attach a CSV file.", "danger")
        return redirect(url_for("admin.import_view"))

    if not uploaded.filename.lower().endswith(".csv"):
        flash("Only .csv files are accepted.", "danger")
        return redirect(url_for("admin.import_view"))

    file_bytes = uploaded.read()

    # 5 MB limit
    if len(file_bytes) > 5 * 1024 * 1024:
        flash("File is too large (max 5 MB).", "danger")
        return redirect(url_for("admin.import_view"))

    try:
        result = run_import(import_type, file_bytes, dry_run=dry_run)
    except ImportError_ as exc:
        flash(f"Import failed: {exc}", "danger")
        return render_template(
            "admin/import.html",
            import_types=IMPORT_TYPES,
            results=None,
            selected_type=import_type,
        )
    except Exception as exc:
        flash(f"Unexpected error: {exc}", "danger")
        return render_template(
            "admin/import.html",
            import_types=IMPORT_TYPES,
            results=None,
            selected_type=import_type,
        )

    return render_template(
        "admin/import.html",
        import_types=IMPORT_TYPES,
        results=result,
        selected_type=import_type,
    )


@admin_bp.route("/import/template/<import_type>.csv")
@admin_required
def import_template(import_type: str):
    """Generate and download a blank CSV template for the chosen import type."""
    if import_type not in IMPORT_TYPES:
        abort(404)

    cfg = IMPORT_TYPES[import_type]
    schema = cfg["schema"]

    # Build the CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row = all known columns for this import type
    columns = schema["all"]
    writer.writerow(columns)

    # One example row (helpful for admins)
    example = _example_row(import_type, columns)
    writer.writerow(example)

    csv_bytes = output.getvalue().encode("utf-8")

    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={import_type}_template.csv"
        },
    )


def _example_row(import_type: str, columns: list[str]) -> list[str]:
    """Return a single helpful example row for the given import type."""
    examples = {
        "universities": {
            "name": "Example University",
            "country": "Exampleland",
            "state_region": "Example Region",
            "city": "Example City",
            "website_url": "https://example.edu",
            "official_email": "info@example.edu",
            "description": "A sample university.",
            "source_url": "https://example.edu/about",
        },
        "programmes": {
            "university_name": "Example University",
            "programme_name": "MSc Computer Science",
            "degree_level": "Master",
            "field": "Computer Science",
            "specialization": "Artificial Intelligence",
            "language": "English",
            "study_mode": "Full-time",
            "duration": "2 years",
            "programme_url": "https://example.edu/msc-cs",
            "application_url": "https://example.edu/apply",
        },
        "requirements": {
            "university_name": "Example University",
            "programme_name": "MSc Computer Science",
            "degree_level": "Master",
            "minimum_cgpa": "3.0",
            "minimum_cgpa_scale": "4.0",
            "minimum_degree": "Bachelor's degree in Computer Science",
            "required_field": "Computer Science",
            "english_requirement": "IELTS 6.5 or TOEFL 90",
            "ielts_required": "true",
            "ielts_minimum_score": "6.5",
            "toefl_required": "true",
            "toefl_minimum_score": "90",
            "gre_required": "false",
            "work_experience_required": "",
            "other_requirements": "",
            "source_url": "https://example.edu/msc-cs/requirements",
        },
        "scholarships": {
            "scholarship_id": "SCH-001",
            "scholarship_name": "Example Scholarship",
            "provider": "Example Foundation",
            "country": "Exampleland",
            "study_level": "Master",
            "eligible_field": "Any",
            "funding_type": "Full tuition",
            "tuition_coverage": "true",
            "living_allowance": "true",
            "travel_allowance": "false",
            "insurance_coverage": "true",
            "amount": "20000",
            "currency": "USD",
            "eligible_nationalities": "International",
            "deadline": "2026-12-31",
            "eligibility": "Open to international students.",
            "scholarship_url": "https://example.org/scholarship",
        },
    }
    example = examples.get(import_type, {})
    return [example.get(c, "") for c in columns]
"""
CSV import service for admin bulk uploads.

Handles four data types, all idempotent:
  - universities
  - programmes (auto-creates universities if missing)
  - admission_requirements (must reference existing programmes)
  - scholarships

Every import is validated before any writes:
  - Header must include all required columns (else reject whole file)
  - Each row validated individually; bad rows are skipped, good rows imported
"""

import csv
import io
from typing import Any

from services.supabase_service import get_admin_client


# ============================================================
# Expected schemas — defines which columns each import needs.
# `required` columns must be present in the CSV header or we reject.
# `optional` columns may be present or absent.
# ============================================================

UNIVERSITY_SCHEMA = {
    "required": ["name", "country"],
    "optional": [
        "state_region", "city", "website_url", "official_email",
        "description", "source_url",
    ],
    "all": [
        "name", "country", "state_region", "city", "website_url",
        "official_email", "description", "source_url",
    ],
}

PROGRAMME_SCHEMA = {
    "required": ["university_name", "programme_name", "degree_level"],
    "optional": [
        "field", "specialization", "language", "study_mode", "duration",
        "programme_url", "application_url",
    ],
    "all": [
        "university_name", "programme_name", "degree_level", "field",
        "specialization", "language", "study_mode", "duration",
        "programme_url", "application_url",
    ],
}

REQUIREMENT_SCHEMA = {
    "required": ["university_name", "programme_name", "degree_level"],
    "optional": [
        "minimum_cgpa", "minimum_cgpa_scale", "minimum_degree",
        "required_field", "english_requirement",
        "ielts_required", "ielts_minimum_score",
        "toefl_required", "toefl_minimum_score", "gre_required",
        "work_experience_required", "other_requirements", "source_url",
    ],
    "all": [
        "university_name", "programme_name", "degree_level",
        "minimum_cgpa", "minimum_cgpa_scale", "minimum_degree",
        "required_field", "english_requirement",
        "ielts_required", "ielts_minimum_score",
        "toefl_required", "toefl_minimum_score", "gre_required",
        "work_experience_required", "other_requirements", "source_url",
    ],
}

SCHOLARSHIP_SCHEMA = {
    "required": ["scholarship_name"],
    "optional": [
        "scholarship_id", "provider", "country", "study_level",
        "eligible_field", "funding_type", "tuition_coverage",
        "living_allowance", "travel_allowance", "insurance_coverage",
        "amount", "currency", "eligible_nationalities",
        "deadline", "eligibility", "scholarship_url",
    ],
    "all": [
        "scholarship_id", "scholarship_name", "provider", "country",
        "study_level", "eligible_field", "funding_type",
        "tuition_coverage", "living_allowance", "travel_allowance",
        "insurance_coverage", "amount", "currency",
        "eligible_nationalities", "deadline", "eligibility",
        "scholarship_url",
    ],
}


IMPORT_TYPES = {
    "universities": {
        "label": "Universities",
        "schema": UNIVERSITY_SCHEMA,
        "help": (
            "Required columns: name, country. "
            "Optional: state_region, city, website_url, official_email, "
            "description, source_url."
        ),
    },
    "programmes": {
        "label": "Programmes",
        "schema": PROGRAMME_SCHEMA,
        "help": (
            "Required columns: university_name, programme_name, degree_level. "
            "Optional: field, specialization, language, study_mode, duration, "
            "programme_url, application_url. Universities are auto-created if missing."
        ),
    },
    "requirements": {
        "label": "Admission Requirements",
        "schema": REQUIREMENT_SCHEMA,
        "help": (
            "Required columns: university_name, programme_name, degree_level. "
            "Match against existing programmes. Programme must already exist."
        ),
    },
    "scholarships": {
        "label": "Scholarships",
        "schema": SCHOLARSHIP_SCHEMA,
        "help": (
            "Required column: scholarship_name. "
            "Optional: provider, country, study_level, funding_type, amount, deadline, "
            "scholarship_url, etc."
        ),
    },
}


# ============================================================
# Validation helpers
# ============================================================

class ImportError_(Exception):
    """Raised when the whole file fails to parse (bad header, wrong format)."""


def _clean(v: Any) -> Any:
    """Empty string -> None. 'true'/'false' -> bool. Whitespace stripped."""
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        if v == "":
            return None
        low = v.lower()
        if low == "true":
            return True
        if low == "false":
            return False
        return v
    return v


def validate_csv_header(fieldnames: list[str], schema: dict) -> None:
    """
    Ensure the CSV header contains all required columns.

    Raises ImportError_ with a helpful message if not.
    """
    if not fieldnames:
        raise ImportError_("CSV file has no header row.")

    # Normalize: lowercase, strip BOM/whitespace
    normalized = {(f or "").strip().lower().lstrip("\ufeff") for f in fieldnames}

    missing = [c for c in schema["required"] if c not in normalized]
    if missing:
        raise ImportError_(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Expected at least: {', '.join(schema['required'])}."
        )


def parse_csv(file_bytes: bytes) -> tuple[list[str], list[dict]]:
    """
    Parse a CSV from raw bytes. Returns (fieldnames, rows).

    Handles BOM, various encodings.
    """
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = file_bytes.decode("latin-1")
        except Exception as e:
            raise ImportError_(f"Could not decode CSV: {e}") from e

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    rows = list(reader)
    return fieldnames, rows


# ============================================================
# Import functions — one per data type
# ============================================================

def _find_or_create_university(client, name: str, country: str | None,
                              city: str | None, dry_run: bool) -> int | None:
    """Return id of university by name; auto-create if missing."""
    name = (name or "").strip()
    if not name:
        return None

    existing = (
        client.table("universities")
        .select("id")
        .eq("name", name)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]["id"]

    if dry_run:
        return -1  # placeholder id, no real insert

    resp = client.table("universities").insert({
        "name": name,
        "country": country or "Unknown",
        "city": city,
        "status": "pending_verification",
    }).execute()
    return resp.data[0]["id"]


def import_universities(rows: list[dict], dry_run: bool) -> dict:
    """Import/update universities keyed by `name`."""
    client = get_admin_client()
    inserted = 0
    updated = 0
    skipped: list[str] = []

    for i, row in enumerate(rows, start=2):
        name = _clean(row.get("name"))
        country = _clean(row.get("country"))
        if not name:
            skipped.append(f"Line {i}: missing name")
            continue
        if not country:
            skipped.append(f"Line {i}: missing country for '{name}'")
            continue

        payload = {
            "name": name,
            "country": country,
            "state_region": _clean(row.get("state_region")),
            "city": _clean(row.get("city")),
            "website_url": _clean(row.get("website_url")),
            "official_email": _clean(row.get("official_email")),
            "description": _clean(row.get("description")),
            "source_url": _clean(row.get("source_url")),
            "status": "active",
        }

        existing = (
            client.table("universities")
            .select("id")
            .eq("name", name)
            .limit(1)
            .execute()
        )

        if existing.data:
            if not dry_run:
                client.table("universities").update(payload).eq(
                    "id", existing.data[0]["id"]
                ).execute()
            updated += 1
        else:
            if not dry_run:
                client.table("universities").insert(payload).execute()
            inserted += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "total": len(rows),
    }


def import_programmes(rows: list[dict], dry_run: bool) -> dict:
    """Import/update programmes. Auto-creates universities by name."""
    client = get_admin_client()
    inserted = 0
    updated = 0
    skipped: list[str] = []
    created_unis = 0

    for i, row in enumerate(rows, start=2):
        uni_name = _clean(row.get("university_name"))
        prog_name = _clean(row.get("programme_name"))
        degree = _clean(row.get("degree_level"))

        if not uni_name:
            skipped.append(f"Line {i}: missing university_name")
            continue
        if not prog_name:
            skipped.append(f"Line {i}: missing programme_name for '{uni_name}'")
            continue
        if not degree:
            skipped.append(f"Line {i}: missing degree_level for '{uni_name}' / '{prog_name}'")
            continue

        # Auto-create university if missing
        uni_id = _find_or_create_university(client, uni_name, None, None, dry_run)
        if uni_id is None or uni_id < 0:
            if dry_run:
                created_unis += 1
            continue
        if not dry_run and uni_id:
            # Count only if it was actually created — check if it existed pre-insert
            pass

        payload = {
            "university_id": uni_id,
            "programme_name": prog_name[:300],
            "degree_level": degree[:100],
            "field": _clean(row.get("field")),
            "specialization": _clean(row.get("specialization")),
            "language": _clean(row.get("language")),
            "study_mode": _clean(row.get("study_mode")),
            "duration": _clean(row.get("duration")),
            "programme_url": _clean(row.get("programme_url")),
            "application_url": _clean(row.get("application_url")),
            "status": "active",
        }

        existing = (
            client.table("programmes")
            .select("id")
            .eq("university_id", uni_id)
            .eq("programme_name", prog_name[:300])
            .eq("degree_level", degree[:100])
            .limit(1)
            .execute()
        )

        if existing.data:
            if not dry_run:
                client.table("programmes").update(payload).eq(
                    "id", existing.data[0]["id"]
                ).execute()
            updated += 1
        else:
            if not dry_run:
                client.table("programmes").insert(payload).execute()
            inserted += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "total": len(rows),
        "created_universities": created_unis,
    }


def import_requirements(rows: list[dict], dry_run: bool) -> dict:
    """
    Import requirements for existing programmes.

    Requires the programme to already exist. Rows referencing
    unknown programmes are skipped with a clear reason.
    """
    client = get_admin_client()
    inserted = 0
    updated = 0
    skipped: list[str] = []

    for i, row in enumerate(rows, start=2):
        uni_name = _clean(row.get("university_name"))
        prog_name = _clean(row.get("programme_name"))
        degree = _clean(row.get("degree_level"))

        if not (uni_name and prog_name and degree):
            skipped.append(f"Line {i}: missing university_name/programme_name/degree_level")
            continue

        # Find the university
        uni_resp = (
            client.table("universities")
            .select("id")
            .eq("name", uni_name)
            .limit(1)
            .execute()
        )
        if not uni_resp.data:
            skipped.append(f"Line {i}: university not found: '{uni_name}'")
            continue
        uni_id = uni_resp.data[0]["id"]

        # Find the programme
        prog_resp = (
            client.table("programmes")
            .select("id")
            .eq("university_id", uni_id)
            .eq("programme_name", prog_name[:300])
            .eq("degree_level", degree[:100])
            .limit(1)
            .execute()
        )
        if not prog_resp.data:
            skipped.append(
                f"Line {i}: programme not found: '{uni_name}' / '{prog_name}' ({degree})"
            )
            continue
        prog_id = prog_resp.data[0]["id"]

        payload = {
            "programme_id": prog_id,
            "minimum_cgpa": _clean(row.get("minimum_cgpa")),
            "minimum_cgpa_scale": _clean(row.get("minimum_cgpa_scale")),
            "minimum_degree": _clean(row.get("minimum_degree")),
            "required_field": _clean(row.get("required_field")),
            "english_requirement": _clean(row.get("english_requirement")),
            "ielts_required": _clean(row.get("ielts_required")),
            "ielts_minimum_score": _clean(row.get("ielts_minimum_score")),
            "toefl_required": _clean(row.get("toefl_required")),
            "toefl_minimum_score": _clean(row.get("toefl_minimum_score")),
            "gre_required": _clean(row.get("gre_required")),
            "work_experience_required": _clean(row.get("work_experience_required")),
            "other_requirements": _clean(row.get("other_requirements")),
            "source_url": _clean(row.get("source_url")),
            "verification_status": "unverified",
        }

        existing = (
            client.table("admission_requirements")
            .select("id")
            .eq("programme_id", prog_id)
            .limit(1)
            .execute()
        )

        if existing.data:
            if not dry_run:
                client.table("admission_requirements").update(payload).eq(
                    "programme_id", prog_id
                ).execute()
            updated += 1
        else:
            if not dry_run:
                client.table("admission_requirements").insert(payload).execute()
            inserted += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "total": len(rows),
    }


def import_scholarships(rows: list[dict], dry_run: bool) -> dict:
    """Import scholarships keyed by scholarship_id (or scholarship_name if no id)."""
    client = get_admin_client()
    inserted = 0
    updated = 0
    skipped: list[str] = []

    for i, row in enumerate(rows, start=2):
        name = _clean(row.get("scholarship_name"))
        if not name:
            skipped.append(f"Line {i}: missing scholarship_name")
            continue

        payload = {k: _clean(row.get(k)) for k in SCHOLARSHIP_SCHEMA["all"]}

        sid = payload.get("scholarship_id")
        existing = None
        if sid:
            existing = (
                client.table("scholarships")
                .select("id")
                .eq("scholarship_id", sid)
                .limit(1)
                .execute()
            )
        else:
            existing = (
                client.table("scholarships")
                .select("id")
                .eq("scholarship_name", name)
                .limit(1)
                .execute()
            )

        if existing and existing.data:
            if not dry_run:
                client.table("scholarships").update(payload).eq(
                    "id", existing.data[0]["id"]
                ).execute()
            updated += 1
        else:
            if not dry_run:
                client.table("scholarships").insert(payload).execute()
            inserted += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "total": len(rows),
    }


# ============================================================
# Dispatcher
# ============================================================

IMPORTERS = {
    "universities": import_universities,
    "programmes": import_programmes,
    "requirements": import_requirements,
    "scholarships": import_scholarships,
}


def run_import(import_type: str, file_bytes: bytes, dry_run: bool = False) -> dict:
    """
    Top-level entry point. Validates the CSV header, then imports.
    Returns a result dict with inserted/updated/skipped counts.
    """
    if import_type not in IMPORTERS:
        raise ImportError_(f"Unknown import type: {import_type}")

    schema = IMPORT_TYPES[import_type]["schema"]
    fieldnames, rows = parse_csv(file_bytes)
    validate_csv_header(fieldnames, schema)

    if not rows:
        raise ImportError_("CSV file has no data rows.")

    result = IMPORTERS[import_type](rows, dry_run)
    result["import_type"] = import_type
    result["dry_run"] = dry_run
    return result
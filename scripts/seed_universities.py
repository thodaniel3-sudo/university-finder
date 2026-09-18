"""
Seed initial universities, programmes, and admission requirements.

Run this LOCALLY, once, from the project root:

    python scripts/seed_universities.py

It uses the ADMIN client (service_role key) which bypasses RLS.
Never run this from a public endpoint.

The data below is a small, curated starter set. It is intentionally
small — real data collection happens in Phase 17 through a controlled
admin workflow. Values marked 'UNKNOWN' in comments are left NULL in
the database, which the matching engine will report as
'Unknown / insufficient data' (Phase 10).

Idempotent: running it twice will not create duplicates.
"""

import sys
from pathlib import Path

# Allow running this script directly: add project root to sys.path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config  # noqa: E402
from supabase import create_client  # noqa: E402


# ============================================================
# Starter dataset
# ============================================================

UNIVERSITIES = [
    {
        "name": "University of Lagos",
        "country": "Nigeria",
        "state_region": "Lagos",
        "city": "Akoka",
        "website_url": "https://unilag.edu.ng",
        "description": (
            "One of Nigeria's premier federal universities, offering "
            "undergraduate and postgraduate programmes across sciences, "
            "engineering, arts, and management."
        ),
        "official_email": None,  # UNKNOWN — do not invent
        "programmes": [
            {
                "programme_name": "MSc Computer Science",
                "degree_level": "Master",
                "field": "Computer Science",
                "specialization": None,
                "language": "English",
                "study_mode": "Full-time",
                "duration": "2 years",
                "programme_url": "https://unilag.edu.ng",
                "application_url": None,
                "requirements": {
                    "minimum_cgpa": 3.00,
                    "minimum_cgpa_scale": 5.00,
                    "minimum_degree": "Bachelor's degree in Computer Science or related field",
                    "required_field": "Computer Science or related",
                    "english_requirement": "English is the language of instruction",
                    "ielts_required": False,
                    "toefl_required": False,
                    "gre_required": False,
                    "work_experience_required": None,
                    "other_requirements": None,
                    "source_url": "https://unilag.edu.ng",
                    "verification_status": "unverified",
                },
            },
            {
                "programme_name": "MBA",
                "degree_level": "Master",
                "field": "Business Administration",
                "specialization": None,
                "language": "English",
                "study_mode": "Part-time",
                "duration": "2 years",
                "programme_url": "https://unilag.edu.ng",
                "application_url": None,
                "requirements": {
                    "minimum_cgpa": None,  # UNKNOWN — verify with university
                    "minimum_cgpa_scale": None,
                    "minimum_degree": "Bachelor's degree in any field",
                    "required_field": None,
                    "english_requirement": "English is the language of instruction",
                    "ielts_required": False,
                    "toefl_required": False,
                    "gre_required": False,
                    "work_experience_required": "Typically 2+ years — verify with university",
                    "other_requirements": None,
                    "source_url": "https://unilag.edu.ng",
                    "verification_status": "unverified",
                },
            },
        ],
    },
    {
        "name": "University of Ghana",
        "country": "Ghana",
        "state_region": "Greater Accra",
        "city": "Legon",
        "website_url": "https://www.ug.edu.gh",
        "description": (
            "Ghana's oldest and largest university, located in Legon, "
            "Accra. Offers a wide range of undergraduate and graduate "
            "programmes."
        ),
        "official_email": None,
        "programmes": [
            {
                "programme_name": "MPhil Computer Science",
                "degree_level": "Master",
                "field": "Computer Science",
                "specialization": None,
                "language": "English",
                "study_mode": "Full-time",
                "duration": "2 years",
                "programme_url": "https://www.ug.edu.gh",
                "application_url": None,
                "requirements": {
                    "minimum_cgpa": None,  # UNKNOWN
                    "minimum_cgpa_scale": None,
                    "minimum_degree": "Bachelor's degree in Computer Science or related field",
                    "required_field": "Computer Science",
                    "english_requirement": "English is the language of instruction",
                    "ielts_required": False,
                    "toefl_required": False,
                    "gre_required": False,
                    "work_experience_required": None,
                    "other_requirements": None,
                    "source_url": "https://www.ug.edu.gh",
                    "verification_status": "unverified",
                },
            },
        ],
    },
    {
        "name": "University of Cape Town",
        "country": "South Africa",
        "state_region": "Western Cape",
        "city": "Cape Town",
        "website_url": "https://www.uct.ac.za",
        "description": (
            "Africa's leading university, consistently ranked among the "
            "top universities worldwide. Strong research focus across "
            "sciences, engineering, humanities, and commerce."
        ),
        "official_email": None,
        "programmes": [
            {
                "programme_name": "MSc Computer Science",
                "degree_level": "Master",
                "field": "Computer Science",
                "specialization": None,
                "language": "English",
                "study_mode": "Full-time",
                "duration": "1-2 years",
                "programme_url": "https://www.uct.ac.za",
                "application_url": None,
                "requirements": {
                    "minimum_cgpa": None,
                    "minimum_cgpa_scale": None,
                    "minimum_degree": "Bachelor's degree with Honours in Computer Science or related field",
                    "required_field": "Computer Science",
                    "english_requirement": "English is the language of instruction",
                    "ielts_required": True,
                    "ielts_minimum_score": 6.5,
                    "toefl_required": True,
                    "toefl_minimum_score": 79,
                    "gre_required": False,
                    "work_experience_required": None,
                    "other_requirements": None,
                    "source_url": "https://www.uct.ac.za",
                    "verification_status": "unverified",
                },
            },
        ],
    },
]


# ============================================================
# Seeding logic
# ============================================================

def seed() -> None:
    if not Config.SUPABASE_URL or not Config.SUPABASE_SERVICE_ROLE_KEY:
        raise SystemExit(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env"
        )

    client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)

    for uni in UNIVERSITIES:
        programmes = uni.pop("programmes")

        # Insert university (or fetch existing by unique name).
        existing = (
            client.table("universities")
            .select("id")
            .eq("name", uni["name"])
            .limit(1)
            .execute()
        )
        if existing.data:
            uni_id = existing.data[0]["id"]
            print(f"[=] University exists: {uni['name']} (id={uni_id})")
        else:
            resp = client.table("universities").insert(uni).execute()
            uni_id = resp.data[0]["id"]
            print(f"[+] Inserted university: {uni['name']} (id={uni_id})")

        for prog in programmes:
            requirements = prog.pop("requirements")
            prog["university_id"] = uni_id

            existing_prog = (
                client.table("programmes")
                .select("id")
                .eq("university_id", uni_id)
                .eq("programme_name", prog["programme_name"])
                .eq("degree_level", prog["degree_level"])
                .limit(1)
                .execute()
            )
            if existing_prog.data:
                prog_id = existing_prog.data[0]["id"]
                print(f"    [=] Programme exists: {prog['programme_name']} (id={prog_id})")
            else:
                resp = client.table("programmes").insert(prog).execute()
                prog_id = resp.data[0]["id"]
                print(f"    [+] Inserted programme: {prog['programme_name']} (id={prog_id})")

            # Upsert requirements (one per programme).
            requirements["programme_id"] = prog_id
            existing_req = (
                client.table("admission_requirements")
                .select("id")
                .eq("programme_id", prog_id)
                .limit(1)
                .execute()
            )
            if existing_req.data:
                client.table("admission_requirements").update(requirements).eq(
                    "programme_id", prog_id
                ).execute()
                print(f"        [=] Requirements updated")
            else:
                client.table("admission_requirements").insert(requirements).execute()
                print(f"        [+] Requirements inserted")

    print("\nDone.")


if __name__ == "__main__":
    seed()
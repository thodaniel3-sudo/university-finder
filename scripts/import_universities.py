"""
Import universities and programmes from CSV into Supabase.

Usage:

    # Dry-run: shows what would happen, touches nothing.
    python scripts/import_universities.py --dry-run

    # Real run: inserts/updates.
    python scripts/import_universities.py

    # Re-run any time — idempotent (updates existing, inserts new).

Behaviour:
  - Universities are keyed by `name`. Existing rows are updated,
    missing rows are inserted.
  - Programmes are keyed by (university_id, programme_name, degree_level).
  - Admission requirements are upserted (one row per programme).
  - Blank CSV cells become NULL in the database.
  - `--dry-run` prints the plan without touching Supabase.

This script uses the ADMIN client (service_role key), which bypasses RLS.
It must never be called from the running web app.
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

# Allow running this script directly: add project root to sys.path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config  # noqa: E402
from supabase import create_client  # noqa: E402


DATA_DIR = PROJECT_ROOT / "data" / "seed"
UNIVERSITIES_CSV = DATA_DIR / "universities.csv"
PROGRAMMES_CSV = DATA_DIR / "programmes.csv"


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

def _clean(value: Any) -> Any:
    """
    Normalize a CSV cell to a DB-safe value.

    - "" -> None
    - "true"/"false" (case-insensitive) -> True/False
    - Numeric strings stay as strings; Supabase casts to numeric
    """
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        if v == "":
            return None
        low = v.lower()
        if low == "true":
            return True
        if low == "false":
            return False
        return v
    return value


def _clean_numeric(value: Any) -> Any:
    """Same as _clean but coerces to float where safe."""
    v = _clean(value)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def _clean_int(value: Any) -> Any:
    v = _clean(value)
    if v is None:
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return v


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing CSV file: {path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------
# Row mappers — CSV row -> database dict
# ------------------------------------------------------------

UNIVERSITY_FIELDS = [
    "name", "country", "state_region", "city",
    "website_url", "official_email", "description", "source_url",
]


def university_payload(row: dict[str, str]) -> dict[str, Any]:
    payload = {k: _clean(row.get(k)) for k in UNIVERSITY_FIELDS}
    payload["status"] = "active"
    return payload


PROGRAMME_FIELDS = [
    "programme_name", "degree_level", "field", "specialization",
    "language", "study_mode", "duration",
    "programme_url", "application_url",
]


def programme_payload(row: dict[str, str], university_id: int) -> dict[str, Any]:
    payload = {k: _clean(row.get(k)) for k in PROGRAMME_FIELDS}
    payload["university_id"] = university_id
    payload["status"] = "active"
    return payload


REQUIREMENT_FIELDS = [
    "minimum_degree", "required_field",
    "english_requirement",
    "work_experience_required", "other_requirements",
    "source_url",
]


def requirement_payload(row: dict[str, str], programme_id: int) -> dict[str, Any]:
    payload: dict[str, Any] = {"programme_id": programme_id}

    for k in REQUIREMENT_FIELDS:
        payload[k] = _clean(row.get(k))

    # Numeric fields
    payload["minimum_cgpa"] = _clean_numeric(row.get("minimum_cgpa"))
    payload["minimum_cgpa_scale"] = _clean_numeric(row.get("minimum_cgpa_scale"))
    payload["ielts_minimum_score"] = _clean_numeric(row.get("ielts_minimum_score"))
    payload["toefl_minimum_score"] = _clean_int(row.get("toefl_minimum_score"))

    # Booleans
    payload["ielts_required"] = _clean(row.get("ielts_required"))
    payload["toefl_required"] = _clean(row.get("toefl_required"))
    payload["gre_required"] = _clean(row.get("gre_required"))

    # Default verification status for freshly-imported data
    payload["verification_status"] = "unverified"

    return payload


# ------------------------------------------------------------
# Import logic
# ------------------------------------------------------------

def upsert_university(client, row: dict[str, str], dry_run: bool) -> int | None:
    payload = university_payload(row)
    name = payload["name"]
    if not name:
        print(f"  [!] Skipping university with empty name")
        return None

    existing = (
        client.table("universities")
        .select("id")
        .eq("name", name)
        .limit(1)
        .execute()
    )
    if existing.data:
        uid = existing.data[0]["id"]
        if dry_run:
            print(f"  [DRY] Would update university '{name}' (id={uid})")
        else:
            client.table("universities").update(payload).eq("id", uid).execute()
            print(f"  [=] Updated university '{name}' (id={uid})")
        return uid
    else:
        if dry_run:
            print(f"  [DRY] Would INSERT university '{name}'")
            return -1  # sentinel for dry-run
        resp = client.table("universities").insert(payload).execute()
        uid = resp.data[0]["id"]
        print(f"  [+] Inserted university '{name}' (id={uid})")
        return uid


def upsert_programme(client, row: dict[str, str], university_id: int,
                     dry_run: bool) -> int | None:
    if university_id is None or university_id < 0:
        # Dry-run placeholder: pretend we have an id
        if dry_run:
            print(f"      [DRY] Would INSERT programme '{row.get('programme_name')}'")
            return -1
        return None

    payload = programme_payload(row, university_id)
    name = payload["programme_name"]
    degree = payload["degree_level"]
    if not name or not degree:
        print(f"      [!] Skipping programme with missing name/degree")
        return None

    existing = (
        client.table("programmes")
        .select("id")
        .eq("university_id", university_id)
        .eq("programme_name", name)
        .eq("degree_level", degree)
        .limit(1)
        .execute()
    )
    if existing.data:
        pid = existing.data[0]["id"]
        if dry_run:
            print(f"      [DRY] Would update programme '{name}' ({degree}) (id={pid})")
        else:
            client.table("programmes").update(payload).eq("id", pid).execute()
            print(f"      [=] Updated programme '{name}' ({degree}) (id={pid})")
        return pid
    else:
        if dry_run:
            print(f"      [DRY] Would INSERT programme '{name}' ({degree})")
            return -1
        resp = client.table("programmes").insert(payload).execute()
        pid = resp.data[0]["id"]
        print(f"      [+] Inserted programme '{name}' ({degree}) (id={pid})")
        return pid


def upsert_requirements(client, row: dict[str, str], programme_id: int,
                        dry_run: bool) -> None:
    if programme_id is None or programme_id < 0:
        return

    payload = requirement_payload(row, programme_id)

    existing = (
        client.table("admission_requirements")
        .select("id")
        .eq("programme_id", programme_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        if dry_run:
            print(f"          [DRY] Would update requirements")
        else:
            client.table("admission_requirements").update(payload).eq(
                "programme_id", programme_id
            ).execute()
            print(f"          [=] Requirements updated")
    else:
        if dry_run:
            print(f"          [DRY] Would INSERT requirements")
        else:
            client.table("admission_requirements").insert(payload).execute()
            print(f"          [+] Requirements inserted")


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Import universities and programmes from CSV.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without touching the database.")
    args = parser.parse_args()

    if not Config.SUPABASE_URL or not Config.SUPABASE_SERVICE_ROLE_KEY:
        raise SystemExit(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env"
        )

    client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)

    print(f"Loading: {UNIVERSITIES_CSV}")
    uni_rows = _load_csv(UNIVERSITIES_CSV)
    print(f"  {len(uni_rows)} universities")

    print(f"Loading: {PROGRAMMES_CSV}")
    prog_rows = _load_csv(PROGRAMMES_CSV)
    print(f"  {len(prog_rows)} programmes")

    if args.dry_run:
        print("\n*** DRY RUN — no changes will be made ***\n")
    else:
        print("\n*** LIVE IMPORT — writing to Supabase ***\n")

    # ---- Import universities ----
    print("=== Universities ===")
    uni_id_map: dict[str, int] = {}
    for row in uni_rows:
        name = row.get("name")
        uid = upsert_university(client, row, args.dry_run)
        if name and uid is not None:
            uni_id_map[name] = uid

    # ---- Import programmes + requirements ----
    print("\n=== Programmes ===")
    unmatched = []
    for row in prog_rows:
        uni_name = row.get("university_name")
        uid = uni_id_map.get(uni_name) if uni_name else None
        if uni_name and uid is None:
            unmatched.append(uni_name)
            print(f"  [!] Programme references unknown university: '{uni_name}'")
            continue
        pid = upsert_programme(client, row, uid, args.dry_run)
        if pid is not None:
            upsert_requirements(client, row, pid, args.dry_run)

    print("\n=== Summary ===")
    print(f"Universities processed: {len(uni_rows)}")
    print(f"Programmes processed:   {len(prog_rows)}")
    if unmatched:
        print(f"Unmatched universities: {len(set(unmatched))}")
        for name in sorted(set(unmatched)):
            print(f"  - {name}")

    if args.dry_run:
        print("\n*** Dry run complete. Re-run without --dry-run to apply. ***")
    else:
        print("\nImport complete.")


if __name__ == "__main__":
    main()
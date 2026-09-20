# University Finder and Application Assistant

A Flask + Supabase web application that helps students discover suitable
universities and programmes, evaluate their fit against documented admission
requirements, and track every step of their application journey - from
search to submission.

> **Live app:** https://university-finder-1.onrender.com
>
> This platform provides information and assistance. It does **not**
> guarantee admission. Final decisions are made by the universities.

---

## Features

### Student features

- **Academic profile** - record your degree history, CGPA, IELTS/TOEFL,
  and study intentions once. Used by the matching engine.
- **University and programme discovery** - browse universities by country,
  drill into programmes, and see which requirements are documented.
- **Search** - free-text search across the curated database. When the
  database has no match, results are supplemented with a web search
  (Brave). Web results are clearly labelled as unverified.
- **Transparent matching** - every requirement is evaluated against
  your profile and reported as one of four outcomes:
  - **Meets documented requirement**
  - **Does not appear to meet documented requirement**
  - **Unknown / insufficient data**
  - **Requires manual verification**
- **Save programmes** - bookmark programmes from the database or from
  web search results for later review.
- **Application tracker** - track each application through 11 statuses
  (Not Started, Applied, Interview, Accepted, Rejected, Withdrawn), with
  deadlines, notes, and application URLs.
- **Document vault** - upload CV, transcripts, certificates, and letters
  to Supabase Storage. Files are private to the owner.
- **Email drafting** - generate polite inquiry emails using your profile
  and the programme. Review and edit before handoff to your mail client.
- **Programme requests** - ask us to add a programme that is not yet in
  the curated database.

### Admin features

- **Admin dashboard** - totals for universities, programmes, and
  requirements.
- **CRUD** - add, edit, and toggle status for universities, programmes,
  and admission requirements.
- **Bulk CSV import** - upload thousands of rows at once for
  universities, programmes, requirements, or scholarships. Idempotent
  (safe to re-run). Dry-run mode available.
- **Template downloads** - generate a blank, correctly-formatted CSV for
  each import type.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.14, Flask 3.1 |
| Templates | Jinja2 |
| Styling | Bootstrap 5 (via CDN) |
| Frontend JS | Vanilla JavaScript |
| Database | Supabase Postgres |
| Auth | Supabase Auth |
| Storage | Supabase Storage |
| Web search | Brave Search API |
| Source control | Git + GitHub |
| Hosting | Render (single web service) |
| Production WSGI | Gunicorn |

---

## Project structure

    University_Finder/
    |-- app.py                      Application factory
    |-- config.py                   Configuration from environment variables
    |-- requirements.txt
    |-- Procfile                    Render start command
    |-- render.yaml                 Render service definition
    |-- pytest.ini                  Test configuration
    |-- .env.example                Documented environment variables
    |-- .gitignore
    |-- README.md
    |-- ROADMAP.md
    |
    |-- routes/                     HTTP blueprints
    |   |-- auth_routes.py
    |   |-- profile_routes.py
    |   |-- university_routes.py
    |   |-- programme_routes.py
    |   |-- saved_routes.py
    |   |-- application_routes.py
    |   |-- document_routes.py
    |   |-- email_routes.py
    |   |-- external_routes.py
    |   |-- search_routes.py
    |   `-- admin_routes.py
    |
    |-- services/                   Business logic (no HTTP)
    |   |-- supabase_service.py
    |   |-- auth_service.py
    |   |-- auth_decorators.py
    |   |-- admin_decorators.py
    |   |-- session_refresh.py
    |   |-- profile_service.py
    |   |-- university_service.py
    |   |-- programme_service.py
    |   |-- matching_service.py
    |   |-- saved_service.py
    |   |-- application_service.py
    |   |-- application_statuses.py
    |   |-- document_service.py
    |   |-- email_service.py
    |   |-- email_generator.py
    |   |-- email_handoff.py
    |   |-- email_provider_resend.py   (dormant)
    |   |-- email_purposes.py
    |   |-- external_service.py
    |   |-- external_email_generator.py
    |   |-- search_service.py
    |   |-- web_search_service.py
    |   |-- csv_import_service.py
    |   |-- rate_limit.py
    |   |-- admin_service.py
    |   `-- forms.py
    |
    |-- templates/                  Jinja2 templates
    |   |-- base.html
    |   |-- index.html
    |   |-- about.html
    |   |-- login.html
    |   |-- register.html
    |   |-- dashboard.html
    |   |-- profile.html
    |   |-- universities.html
    |   |-- university.html
    |   |-- programme.html
    |   |-- saved.html
    |   |-- applications.html
    |   |-- application.html
    |   |-- documents.html
    |   |-- emails.html
    |   |-- email.html
    |   |-- email_compose.html
    |   |-- email_review.html
    |   |-- email_send.html
    |   |-- external_detail.html
    |   |-- external_compose.html
    |   |-- search.html
    |   |-- 404.html
    |   |-- 429.html
    |   `-- admin/
    |       |-- dashboard.html
    |       |-- universities.html
    |       |-- university_form.html
    |       |-- programmes.html
    |       |-- programme_form.html
    |       |-- requirements_form.html
    |       `-- import.html
    |
    |-- static/
    |   |-- css/style.css
    |   |-- js/main.js
    |   `-- images/
    |
    |-- scripts/
    |   |-- import_universities.py
    |   `-- scan_for_secrets.py
    |
    |-- data/seed/
    |   |-- universities.csv
    |   |-- programmes.csv
    |   |-- universities_import_1.csv
    |   |-- programmes_import_1.csv
    |   |-- requirements_import_1.csv
    |   |-- scholarships_import_1.csv
    |   `-- Scholarship database.csv
    |
    |-- tests/
    |   |-- conftest.py
    |   |-- test_auth.py
    |   |-- test_search.py
    |   |-- test_matching.py
    |   |-- test_csv_import.py
    |   `-- test_admin.py
    |
    `-- docs/
        |-- DEPLOYMENT.md
        |-- ADMIN_GUIDE.md
        |-- DATA_FORMAT.md
        `-- ARCHITECTURE.md

---

## Local setup

### 1. Prerequisites

- Python 3.14 (or 3.12+)
- Git
- A Supabase account (free tier)
- A Brave Search API key (optional - only needed for web search fallback)

### 2. Clone and install

    git clone https://github.com/thodaniel3-sudo/university-finder.git
    cd university-finder
    py -3.14 -m venv venv
    .\venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt

### 3. Configure environment

    Copy-Item .env.example .env

Then edit `.env` and fill in:

- `FLASK_SECRET_KEY` - generate with
  `python -c "import secrets; print(secrets.token_hex(32))"`
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` -
  from your Supabase project settings (Project Settings -> API)
- `BRAVE_SEARCH_API_KEY` - optional; leave empty to disable web fallback

### 4. Initialise the database

Run the SQL from `docs/DEPLOYMENT.md` in the Supabase SQL Editor to create
the required tables and RLS policies. The full schema is in
`migrations/database.sql`.

### 5. Seed initial data (optional)

    python scripts/import_universities.py

Or use the admin CSV importer once the app is running.

### 6. Run locally

    python -m flask --app app run --debug

Then open http://127.0.0.1:5000

---

## Running tests

    python -m pytest -v

Expected: all tests pass. The suite covers auth, search, matching, CSV
import, and admin authorization.

Tests do not require Supabase credentials - they only exercise the
routes and pure functions that don't hit the database.

---

## Bulk CSV import

Admins can bulk-import four kinds of data through `/admin/import`:

- Universities
- Programmes (auto-creates universities if missing)
- Admission Requirements (must reference existing programmes)
- Scholarships

Each type has a downloadable template on the import page. See
`docs/DATA_FORMAT.md` for column definitions.

---

## Security

- **Supabase Row Level Security (RLS)** on every user-owned table.
  Students can only read/write their own profile, saved programmes,
  applications, documents, and emails.
- **CSRF protection** on all POST routes (Flask-WTF `CSRFProtect`).
- **Rate limiting** on `/login` and `/register` (Flask-Limiter).
- **Session cookie hardening**: HttpOnly, SameSite=Lax, Secure in
  production.
- **JWT refresh** - Supabase access tokens are refreshed silently, so
  users stay logged in for weeks.
- **Secret scanning** - `scripts/scan_for_secrets.py` runs on every
  commit via a git pre-commit hook. It blocks commits containing strings
  that look like API keys, JWTs, or private keys.

### Rotating a leaked key

1. Log in to the provider (Brave, Resend, Supabase, etc.).
2. Delete the leaked key.
3. Generate a new one.
4. Paste the new value into `.env` (local) **and** Render's Environment
   tab (production).
5. Restart the app.

### Pre-commit scan

Run the secret scanner manually before committing:

    python scripts/scan_for_secrets.py

If it finds anything that looks like a real key, fix it before pushing.
The git pre-commit hook does this automatically if the hook is installed.

---

## Deployment

The app is deployed as a **single Render Web Service** (free tier).

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn app:app`
- **Environment variables:** configured in the Render dashboard, never
  in the repository.

See `docs/DEPLOYMENT.md` for the full step-by-step.

---

## Roadmap

See `ROADMAP.md` for planned future features.

---

## License

This is a personal project. Contact the author for use.
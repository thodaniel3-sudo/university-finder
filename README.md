# University Finder and Application Assistant

A Flask + Supabase web application that helps students find suitable
universities and programmes, track applications, and contact universities
through a review-and-confirm email workflow.

## Status

Phase 5 — Frontend foundation (base template, Bootstrap 5, homepage, about page).

## Stack

- Python 3.14
- Flask 3.1 + Jinja2
- Bootstrap 5 + vanilla JavaScript
- Supabase (Postgres, Auth, Storage) — added in Phase 7
- Resend (transactional email) via a service layer — added in Phase 16
- Render (production hosting) — added in Phase 22

## Local setup

    py -3.14 -m venv venv
    .\venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt

Copy `.env.example` to `.env` and fill in the values.

## Run locally

    python -m flask --app app run --debug

Then open http://127.0.0.1:5000

## Project layout

    University_Finder/
    ├── app.py                 # Application factory and routes
    ├── config.py              # Configuration from environment variables
    ├── requirements.txt
    ├── .env                   # Secrets (never committed)
    ├── .env.example           # Documented variables (safe to commit)
    ├── .gitignore
    ├── README.md
    ├── routes/                # Blueprints (added in later phases)
    ├── services/              # Business logic (Supabase, email, matching)
    ├── models/                # Data structures
    ├── templates/             # Jinja2 templates
    │   ├── base.html          # Master layout
    │   ├── index.html         # Homepage
    │   └── about.html         # About page
    ├── static/
    │   ├── css/style.css
    │   ├── js/main.js
    │   └── images/
    ├── tests/                 # Pytest tests
    ├── scripts/               # Data collection / maintenance scripts
    ├── migrations/            # Database schema (SQL)
    └── data/seed/             # Seed data

## Development phases

Building incrementally. Phase 5 (Frontend foundation) is complete.
Phase 6 (Supabase project and database) is next.

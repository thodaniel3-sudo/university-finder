# University Finder and Application Assistant

A Flask + Supabase web application that helps students find suitable
universities and programmes, track applications, and contact universities
through a review-and-confirm email workflow.

## Status

Phase 2 — development environment set up.

## Stack

- Python 3.12
- Flask 3.x + Jinja2
- Bootstrap 5 + vanilla JavaScript (Phase 5)
- Supabase (Postgres, Auth, Storage)
- Resend (transactional email) via a service layer
- Render (production hosting)

## Local setup

    py -3.12 -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt

Copy `.env.example` to `.env` and fill in the values.

## Run locally

    flask --app app run --debug

Then open http://127.0.0.1:5000

## Development phases

We build this project in 26 documented phases. Phase 2 is complete.
Phase 3 (Flask foundation) is next.

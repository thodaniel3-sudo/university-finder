"""
Shared pytest fixtures for the University Finder test suite.

Key design choices:
  - We use Flask's built-in test client so we exercise the real app.
  - We don't touch Supabase at all. Tests that would call Supabase
    are either skipped or use mocks. This keeps the test suite fast
    and independent of network state.
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path so `from app import ...` works.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Force test-friendly env vars before app is imported.
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-not-for-production")
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("SUPABASE_URL", "")
os.environ.setdefault("SUPABASE_ANON_KEY", "")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "")
os.environ.setdefault("BRAVE_SEARCH_API_KEY", "")


from app import create_app  # noqa: E402
from config import Config  # noqa: E402


class TestConfig(Config):
    """Override config for tests."""
    TESTING = True
    WTF_CSRF_ENABLED = False       # disable CSRF for form posts in tests
    SERVER_NAME = "localhost"


@pytest.fixture(scope="session")
def app():
    """Session-scoped Flask app for all tests."""
    application = create_app(TestConfig)
    return application


@pytest.fixture()
def client(app):
    """A Flask test client. Each test gets a fresh client."""
    return app.test_client()


@pytest.fixture()
def runner(app):
    """Flask CLI runner for testing commands."""
    return app.test_cli_runner()


@pytest.fixture()
def logged_out_client(client):
    """Client with no session. Just returns `client` — sessions are per-request."""
    with client.session_transaction() as sess:
        sess.clear()
    return client
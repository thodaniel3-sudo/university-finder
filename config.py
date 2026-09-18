import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration shared by all environments."""

    # Flask
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")

    # Session cookie hardening
    SESSION_COOKIE_HTTPONLY = True   # JavaScript cannot read the cookie
    SESSION_COOKIE_SAMESITE = "Lax"  # sent on top-level GETs, blocks most CSRF
    SESSION_COOKIE_SECURE = False    # set True in production (HTTPS only)
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7  # 7 days

    # Supabase
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    # Email
    EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "resend")
    EMAIL_API_KEY = os.environ.get("EMAIL_API_KEY", "")
    EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
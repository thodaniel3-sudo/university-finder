import os

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    """
    Read an environment variable and strip surrounding whitespace.

    Prevents the common bug where `.env` files have a space after `=`,
    e.g. `KEY= BSA...` — the space would otherwise become part of the value.
    """
    raw = os.environ.get(name, default)
    if raw is None:
        return default
    return raw.strip()


class Config:
    """Base configuration shared by all environments."""

    # Flask
    SECRET_KEY = _env("FLASK_SECRET_KEY", "dev-only-change-me")
    FLASK_ENV = _env("FLASK_ENV", "development")

       # Session cookie hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # In production (HTTPS), cookies must be Secure=True.
    # We read from env so local HTTP dev still works.
    SESSION_COOKIE_SECURE = _env("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7  # 7 days

    # Supabase
    SUPABASE_URL = _env("SUPABASE_URL")
    SUPABASE_ANON_KEY = _env("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY = _env("SUPABASE_SERVICE_ROLE_KEY")

    # Web search (Brave Search API)
    BRAVE_SEARCH_API_KEY = _env("BRAVE_SEARCH_API_KEY")

    # Email
    EMAIL_PROVIDER = _env("EMAIL_PROVIDER", "resend")
    EMAIL_API_KEY = _env("EMAIL_API_KEY")
    EMAIL_FROM = _env("EMAIL_FROM")
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

    # Canonical host for SEO (used for redirects and canonical URLs)
    PREFERRED_HOST = _env("PREFERRED_HOST", "https://university-finder.me")

    # Session cookie hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = _env("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = _env("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7  # 7 days

    # Supabase
    SUPABASE_URL = _env("SUPABASE_URL")
    SUPABASE_ANON_KEY = _env("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY = _env("SUPABASE_SERVICE_ROLE_KEY")

    # Web search (Brave Search API)
    BRAVE_SEARCH_API_KEY = _env("BRAVE_SEARCH_API_KEY")

    # YouTube Data API v3
    YOUTUBE_API_KEY = _env("YOUTUBE_API_KEY")

    # Apify (for scholarship scraping)
    APIFY_TOKEN = _env("APIFY_TOKEN")

    # Reddit API (for Reddit discussions on page 2)
    REDDIT_CLIENT_ID = _env("REDDIT_CLIENT_ID")
    REDDIT_CLIENT_SECRET = _env("REDDIT_CLIENT_SECRET")
    REDDIT_USER_AGENT = _env(
        "REDDIT_USER_AGENT",
        "university-finder/1.0 by u/anonymous",
    )

    # Meta / Facebook OAuth
    META_APP_ID = _env("META_APP_ID")
    META_APP_SECRET = _env("META_APP_SECRET")
    META_REDIRECT_URI = _env(
        "META_REDIRECT_URI",
        "http://localhost:5000/facebook/callback",
    )

    # Email
    EMAIL_PROVIDER = _env("EMAIL_PROVIDER", "resend")
    EMAIL_API_KEY = _env("EMAIL_API_KEY")
    EMAIL_FROM = _env("EMAIL_FROM")
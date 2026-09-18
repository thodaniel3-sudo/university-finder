"""
Supabase client factory.

Two clients are exposed:

- get_public_client()  -> uses the anon key. Safe for user-scoped reads,
                          and the one we'll use for auth in Phase 7.

- get_admin_client()   -> uses the service_role key. Bypasses Row Level
                          Security. MUST only be used inside server-side
                          code that legitimately needs admin access
                          (data seeding, admin dashboard, verifications).
                          NEVER send this client to the browser.

Both clients are cached so we don't create a new HTTP connection pool on
every request.
"""

from functools import lru_cache

from flask import current_app
from supabase import Client, create_client


@lru_cache(maxsize=1)
def _build_client(url: str, key: str) -> Client:
    """Internal builder — cached on (url, key)."""
    return create_client(url, key)


def get_public_client() -> Client:
    """Return a Supabase client using the anon key."""
    cfg = current_app.config
    return _build_client(cfg["SUPABASE_URL"], cfg["SUPABASE_ANON_KEY"])


def get_admin_client() -> Client:
    """Return a Supabase client using the service_role key."""
    cfg = current_app.config
    if not cfg.get("SUPABASE_SERVICE_ROLE_KEY"):
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is not set. "
            "Admin operations are unavailable."
        )
    return _build_client(cfg["SUPABASE_URL"], cfg["SUPABASE_SERVICE_ROLE_KEY"])
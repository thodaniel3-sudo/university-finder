"""
Supabase client factory.

Three clients are exposed:

- get_public_client()    -> anon key, no user identity. Used for auth
                            (register, login), and reading public tables.

- get_admin_client()     -> service_role key. Bypasses RLS. Only for
                            server-side admin operations (seeding,
                            verification scripts, admin dashboard).

- get_user_client()      -> anon key + the current user's access token.
                            Every request against a protected table
                            runs AS that user, respecting RLS.

Clients are cached on (url, key) so we don't rebuild HTTP pools.
The user client is NOT cached — it changes per request based on the
current session's access token.
"""

from functools import lru_cache

from flask import current_app
from supabase import Client, create_client


@lru_cache(maxsize=4)
def _build_client(url: str, key: str) -> Client:
    return create_client(url, key)


def get_public_client() -> Client:
    """Anonymous client — no user identity."""
    cfg = current_app.config
    return _build_client(cfg["SUPABASE_URL"], cfg["SUPABASE_ANON_KEY"])


def get_admin_client() -> Client:
    """Service-role client. Bypasses RLS. Server-side only."""
    cfg = current_app.config
    if not cfg.get("SUPABASE_SERVICE_ROLE_KEY"):
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is not set. "
            "Admin operations are unavailable."
        )
    return _build_client(cfg["SUPABASE_URL"], cfg["SUPABASE_SERVICE_ROLE_KEY"])


def get_user_client(access_token: str) -> Client:
    """
    Build a fresh client that acts AS the given user.

    Not cached — the access token changes per session and we don't
    want stale JWTs lingering in memory.
    """
    cfg = current_app.config
    client = create_client(cfg["SUPABASE_URL"], cfg["SUPABASE_ANON_KEY"])
    # Attach the JWT so postgrest includes it in the Authorization header.
    client.postgrest.auth(access_token)
    return client
"""
Authentication service.

Wraps Supabase Auth so the rest of the app never talks to the auth API
directly. If we ever swap providers, only this file changes.

IMPORTANT: This service uses the PUBLIC (anon) client, never the
service_role client. Supabase Auth is designed to be called with the
anon key — the anon key is safe because it cannot bypass RLS.
"""

from typing import Any

from services.supabase_service import get_public_client


class AuthError(Exception):
    """Raised when an auth operation fails. Message is user-safe."""


def register_user(email: str, password: str) -> dict[str, Any]:
    """
    Create a new user in Supabase Auth.

    Returns the user dict on success.
    Raises AuthError with a user-friendly message on failure.
    """
    client = get_public_client()
    try:
        response = client.auth.sign_up({"email": email, "password": password})
    except Exception as exc:
        # Supabase SDK raises on network / API errors.
        # Never expose the raw exception to users.
        raise AuthError("Could not reach the authentication service. "
                        "Please try again.") from exc

    if response.user is None:
        raise AuthError("Registration failed. Please try again.")

    return {
        "id": response.user.id,
        "email": response.user.email,
        "email_confirmed": bool(getattr(response.user, "email_confirmed_at", None)),
    }


def authenticate_user(email: str, password: str) -> dict[str, Any]:
    """
    Log in an existing user.

    Returns a dict with user info and session tokens.
    Raises AuthError on failure.
    """
    client = get_public_client()
    try:
        response = client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception as exc:
        # Supabase returns "Invalid login credentials" for both
        # wrong email and wrong password — good, we don't leak which.
        raise AuthError("Invalid email or password.") from exc

    if response.user is None or response.session is None:
        raise AuthError("Invalid email or password.")

        expires_at = getattr(response.session, "expires_at", None)

    return {
        "id": response.user.id,
        "email": response.user.email,
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "expires_at": int(expires_at) if expires_at else 0,
    }


def sign_out_user(access_token: str) -> None:
    """
    Revoke a Supabase session server-side.

    Best-effort — if it fails we still clear the local Flask session.
    """
    client = get_public_client()
    try:
        client.auth.sign_out()  # SDK uses the token set on the client
    except Exception:
        # Nothing we can do — session will expire on Supabase anyway.
        pass


def refresh_session(refresh_token: str) -> dict[str, Any]:
    """
    Exchange a refresh token for a new access token.

    Returns:
        {
            "access_token": str,
            "refresh_token": str,
            "expires_at": int,   # unix timestamp
        }

    Raises AuthError if the refresh token itself is expired or revoked.
    """
    client = get_public_client()
    try:
        response = client.auth.refresh_session(refresh_token)
    except Exception as exc:
        raise AuthError("Your session has expired. Please log in again.") from exc

    if response.session is None:
        raise AuthError("Your session has expired. Please log in again.")

    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "expires_at": int(response.session.expires_at),
    }
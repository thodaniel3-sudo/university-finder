

"""
Authentication service.

Wraps Supabase Auth so the rest of the app never talks to the auth API
directly. Uses the PUBLIC (anon) client — never the service_role client.
"""

from typing import Any

from services.supabase_service import get_public_client


class AuthError(Exception):
    """Raised when an auth operation fails. Message is user-safe."""


def register_user(email: str, password: str) -> dict[str, Any]:
    client = get_public_client()
    try:
        response = client.auth.sign_up({"email": email, "password": password})
    except Exception as exc:
        raise AuthError(
            "Could not reach the authentication service. Please try again."
        ) from exc

    if response.user is None:
        raise AuthError("Registration failed. Please try again.")

    return {
        "id": response.user.id,
        "email": response.user.email,
        "email_confirmed": bool(getattr(response.user, "email_confirmed_at", None)),
    }


def authenticate_user(email: str, password: str) -> dict[str, Any]:
    client = get_public_client()
    try:
        response = client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception as exc:
        raise AuthError("Invalid email or password.") from exc

    if response.user is None or response.session is None:
        raise AuthError("Invalid email or password.")

    # expires_at is read HERE, on the success path, AFTER the guard above.
    expires_at = getattr(response.session, "expires_at", None)

    return {
        "id": response.user.id,
        "email": response.user.email,
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "expires_at": int(expires_at) if expires_at else 0,
    }


def sign_out_user(access_token: str) -> None:
    client = get_public_client()
    try:
        client.auth.sign_out()
    except Exception:
        pass


def refresh_session(refresh_token: str) -> dict[str, Any]:
    client = get_public_client()
    try:
        response = client.auth.refresh_session(refresh_token)
    except Exception as exc:
        raise AuthError("Your session has expired. Please log in again.") from exc

    if response.session is None:
        raise AuthError("Your session has expired. Please log in again.")

    expires_at = getattr(response.session, "expires_at", None)

    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "expires_at": int(expires_at) if expires_at else 0,
    }
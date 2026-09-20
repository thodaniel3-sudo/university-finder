"""
Tests for authentication routes and decorators.

These tests do NOT hit Supabase Auth. They verify:
  - Routes exist and behave correctly without credentials
  - The @login_required decorator protects routes
  - GET/POST methods are handled
"""

import pytest


class TestPublicRoutes:
    """Homepage, about, and 404 are open to everyone."""

    def test_homepage_renders(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert b"University Finder" in response.data

    def test_about_renders(self, client):
        response = client.get("/about")
        assert response.status_code == 200
        assert b"About" in response.data

    def test_404_custom_page(self, client):
        response = client.get("/this-page-does-not-exist")
        assert response.status_code == 404
        # The custom 404 template contains this text
        assert b"404" in response.data or b"not found" in response.data.lower()


class TestLoginRoute:
    """The /login route should render GET and accept POST."""

    def test_login_page_renders(self, client):
        response = client.get("/login")
        assert response.status_code == 200
        assert b"Log in" in response.data or b"login" in response.data.lower()

    def test_login_requires_email_and_password(self, client):
        # POST with empty body should not crash — just re-render
        response = client.post("/login", data={})
        # Should render the form again (with error messages)
        assert response.status_code == 200


class TestRegisterRoute:
    """The /register route should render GET and accept POST."""

    def test_register_page_renders(self, client):
        response = client.get("/register")
        assert response.status_code == 200
        assert b"Register" in response.data or b"Create account" in response.data

    def test_register_rejects_empty(self, client):
        response = client.post("/register", data={})
        # Should re-render with validation errors
        assert response.status_code == 200


class TestProtectedRoutes:
    """Routes with @login_required should redirect to /login when no session."""

    @pytest.mark.parametrize("path", [
        "/dashboard",
        "/profile",
        "/saved",
        "/applications",
        "/documents",
        "/emails",
        "/admin/",
    ])
    def test_protected_routes_redirect_to_login(self, client, path):
        response = client.get(path, follow_redirects=False)
        # 302 redirect to /login
        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    @pytest.mark.parametrize("path", [
        "/dashboard",
        "/profile",
        "/saved",
        "/emails",
    ])
    def test_protected_routes_redirect_when_followed(self, client, path):
        response = client.get(path, follow_redirects=True)
        # After following the redirect, we should land on /login
        assert response.status_code == 200
        assert b"Log in" in response.data or b"login" in response.data.lower()


class TestLogoutRoute:
    """Logout should clear session and redirect to home."""

    def test_logout_redirects_to_index(self, client):
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 302
        assert "/" in response.headers.get("Location", "")

    def test_logout_clears_session(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = "fake-user-id"
            sess["user_email"] = "fake@example.com"

        client.get("/logout")

        with client.session_transaction() as sess:
            assert "user_id" not in sess
            assert "user_email" not in sess
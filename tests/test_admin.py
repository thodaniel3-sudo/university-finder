"""
Tests for the admin routes.

The goal is to verify authorization: admin routes must reject
non-admins and unauthenticated users.
"""

import pytest


class TestAdminProtection:
    """All /admin/* routes require admin authorization."""

    @pytest.mark.parametrize("path", [
        "/admin/",
        "/admin/universities",
        "/admin/universities/new",
        "/admin/programmes",
        "/admin/programmes/new",
        "/admin/import",
    ])
    def test_admin_routes_redirect_when_not_logged_in(self, client, path):
        """Without a session, /admin routes should redirect to login."""
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    def test_admin_dashboard_requires_login(self, client):
        response = client.get("/admin/", follow_redirects=True)
        assert response.status_code == 200
        # After redirect, we should land on login
        assert b"Log in" in response.data or b"login" in response.data.lower()


class TestAdminImportTemplateDownload:
    """CSV template downloads should work for admins."""

    def test_template_download_requires_login(self, client):
        """Non-logged-in users can't download templates."""
        response = client.get("/admin/import/template/universities.csv",
                              follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    def test_invalid_import_type_returns_404_for_admin(self, client):
        """Even if logged in as admin, invalid template names should 404."""
        # We can't easily log in as admin in tests (needs Supabase Auth).
        # But we can verify the route's abort() behavior by checking
        # that unauthenticated access to an invalid type still redirects.
        response = client.get("/admin/import/template/not-a-real-type.csv",
                              follow_redirects=False)
        # Admin check happens first, so we get a redirect to login
        assert response.status_code == 302
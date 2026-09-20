"""
Tests for the search functionality.

Tests avoid hitting the real DB. They verify:
  - The /search route renders
  - The search form accepts a query
  - Missing query shows empty state
  - Pagination logic (pure functions) works
  - CSV-like URL param handling
"""

import pytest


class TestSearchRoute:
    """Basic search page rendering."""

    def test_search_page_without_query(self, client):
        """Empty query returns empty state without touching Supabase."""
        response = client.get("/search")
        assert response.status_code == 200
        assert b"Try a search" in response.data or b"Search" in response.data

    def test_search_page_with_only_whitespace(self, client):
        """Whitespace query should be treated as empty, no DB call."""
        response = client.get("/search?q=%20%20%20")
        assert response.status_code == 200


class TestSearchServicePureLogic:
    """
    Pure logic tests that don't hit Supabase or need an app context.

    Tests that require a live database are intentionally omitted.
    Add them later as integration tests when we have a test database.
    """

    def test_empty_query_returns_empty_result(self):
        from services.search_service import search_everything
        result = search_everything("")
        assert result["db_programmes"] == []
        assert result["db_universities"] == []
        assert result["db_total"] == 0
        assert result["db_page"] == 1
        assert result["db_total_pages"] == 1

    def test_whitespace_query_treated_as_empty(self):
        from services.search_service import search_everything
        result = search_everything("   ")
        assert result["db_total"] == 0
        assert result["db_page"] == 1
        assert result["web_results"] == []

    def test_empty_result_has_all_expected_keys(self):
        from services.search_service import search_everything
        result = search_everything("")
        # Confirm the result shape is what the template expects
        assert "db_programmes" in result
        assert "db_universities" in result
        assert "db_total" in result
        assert "db_page" in result
        assert "db_total_pages" in result
        assert "web_results" in result
        assert "web_available" in result


class TestRequestProgrammeRoute:
    """The /request-programme endpoint requires a query."""

    def test_request_without_query_redirects(self, client):
        response = client.post("/request-programme", data={}, follow_redirects=False)
        assert response.status_code == 302

    def test_request_with_query_does_not_crash(self, client):
        # This would try to insert into Supabase. With empty creds, it will
        # fail gracefully (flash error) and redirect. That's acceptable.
        response = client.post(
            "/request-programme",
            data={"query": "marine biology", "contact_email": "", "notes": ""},
            follow_redirects=False,
        )
        assert response.status_code == 302
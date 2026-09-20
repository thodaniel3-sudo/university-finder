"""
Tests for the CSV import service.

These tests verify the pure-logic parts of the importer:
header validation, CSV parsing, and dry-run dispatcher behaviour
without actually writing to Supabase.
"""

import pytest

from services.csv_import_service import (
    IMPORT_TYPES,
    ImportError_,
    parse_csv,
    validate_csv_header,
)


class TestCsvParsing:
    """Parsing CSVs from raw bytes."""

    def test_parses_simple_csv(self):
        data = b"name,country\nUniversity A,Nigeria\nUniversity B,Ghana\n"
        headers, rows = parse_csv(data)
        assert headers == ["name", "country"]
        assert len(rows) == 2
        assert rows[0]["name"] == "University A"

    def test_parses_csv_with_bom(self):
        # BOM (byte order mark) at the start of the file
        data = b"\xef\xbb\xbfname,country\nUniversity A,Nigeria\n"
        headers, rows = parse_csv(data)
        assert headers == ["name", "country"]
        assert len(rows) == 1

    def test_parses_empty_csv(self):
        data = b""
        headers, rows = parse_csv(data)
        assert headers == []
        assert rows == []

    def test_parses_csv_with_quoted_commas(self):
        data = b'name,country\n"University, A",Nigeria\n'
        headers, rows = parse_csv(data)
        assert rows[0]["name"] == "University, A"


class TestHeaderValidation:
    """Header validation against expected schema."""

    def test_accepts_correct_header_universities(self):
        # Should not raise
        validate_csv_header(
            ["name", "country"],
            IMPORT_TYPES["universities"]["schema"],
        )

    def test_rejects_missing_required_column(self):
        with pytest.raises(ImportError_):
            validate_csv_header(
                ["name"],  # missing "country"
                IMPORT_TYPES["universities"]["schema"],
            )

    def test_accepts_extra_columns(self):
        # Extra columns beyond the schema should be tolerated
        validate_csv_header(
            ["name", "country", "extra_column"],
            IMPORT_TYPES["universities"]["schema"],
        )

    def test_accepts_headers_with_whitespace(self):
        validate_csv_header(
            [" name ", " country "],
            IMPORT_TYPES["universities"]["schema"],
        )

    def test_accepts_programme_header(self):
        validate_csv_header(
            ["university_name", "programme_name", "degree_level"],
            IMPORT_TYPES["programmes"]["schema"],
        )

    def test_rejects_empty_header(self):
        with pytest.raises(ImportError_):
            validate_csv_header([], IMPORT_TYPES["universities"]["schema"])


class TestImportTypesRegistry:
    """Sanity checks on the import types registry."""

    def test_all_four_types_defined(self):
        assert "universities" in IMPORT_TYPES
        assert "programmes" in IMPORT_TYPES
        assert "requirements" in IMPORT_TYPES
        assert "scholarships" in IMPORT_TYPES

    def test_each_type_has_label_and_help(self):
        for key, cfg in IMPORT_TYPES.items():
            assert cfg["label"], f"{key} missing label"
            assert cfg["help"], f"{key} missing help"
            assert "schema" in cfg
            assert "required" in cfg["schema"]
            assert "all" in cfg["schema"]
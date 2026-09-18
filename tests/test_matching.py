"""
Tests for the matching engine.

These tests are pure — no database, no Flask app needed.
Run with:  python -m pytest tests/test_matching.py -v
"""

from services.matching_service import (
    MatchStatus,
    check_cgpa,
    check_degree_level,
    check_field,
    check_gre,
    check_ielts,
    check_toefl,
    match_programme,
)


# ---------- CGPA ----------

def test_cgpa_meets_same_scale():
    profile = {"cgpa": 3.5, "cgpa_scale": 4.0}
    req = {"minimum_cgpa": 3.0, "minimum_cgpa_scale": 4.0}
    result = check_cgpa(profile, req)
    assert result.status == MatchStatus.MEETS


def test_cgpa_does_not_meet():
    profile = {"cgpa": 2.5, "cgpa_scale": 4.0}
    req = {"minimum_cgpa": 3.0, "minimum_cgpa_scale": 4.0}
    result = check_cgpa(profile, req)
    assert result.status == MatchStatus.DOES_NOT_MEET


def test_cgpa_across_scales_equivalent():
    """3.2/4.0 == 4.0/5.0 — both are 80% of scale."""
    profile = {"cgpa": 3.2, "cgpa_scale": 4.0}
    req = {"minimum_cgpa": 4.0, "minimum_cgpa_scale": 5.0}
    result = check_cgpa(profile, req)
    assert result.status == MatchStatus.MEETS


def test_cgpa_missing_university_requirement():
    profile = {"cgpa": 3.5, "cgpa_scale": 4.0}
    req = {"minimum_cgpa": None, "minimum_cgpa_scale": None}
    result = check_cgpa(profile, req)
    assert result.status == MatchStatus.UNKNOWN


def test_cgpa_missing_student_value():
    profile = {"cgpa": None, "cgpa_scale": None}
    req = {"minimum_cgpa": 3.0, "minimum_cgpa_scale": 4.0}
    result = check_cgpa(profile, req)
    assert result.status == MatchStatus.UNKNOWN


# ---------- Degree level ----------

def test_degree_bachelor_to_master():
    profile = {"degree_level": "Master", "previous_degree": "BSc Computer Science"}
    result = check_degree_level(profile, {})
    assert result.status == MatchStatus.MEETS


def test_degree_phd_requires_master():
    profile = {"degree_level": "PhD", "previous_degree": "BSc Physics"}
    result = check_degree_level(profile, {})
    assert result.status == MatchStatus.DOES_NOT_MEET


# ---------- Field ----------

def test_field_exact_match():
    profile = {"previous_field": "Computer Science"}
    req = {"required_field": "Computer Science"}
    result = check_field(profile, req)
    assert result.status == MatchStatus.MEETS


def test_field_related_match():
    profile = {"previous_field": "Computer Science"}
    req = {"required_field": "Computer Science or related"}
    result = check_field(profile, req)
    assert result.status == MatchStatus.MEETS


def test_field_no_match():
    profile = {"previous_field": "History"}
    req = {"required_field": "Computer Science"}
    result = check_field(profile, req)
    assert result.status == MatchStatus.DOES_NOT_MEET


def test_field_unknown_when_university_silent():
    profile = {"previous_field": "History"}
    req = {"required_field": None}
    result = check_field(profile, req)
    assert result.status == MatchStatus.UNKNOWN


# ---------- IELTS ----------

def test_ielts_meets():
    profile = {"ielts_score": 7.0}
    req = {"ielts_required": True, "ielts_minimum_score": 6.5}
    result = check_ielts(profile, req)
    assert result.status == MatchStatus.MEETS


def test_ielts_below():
    profile = {"ielts_score": 5.5}
    req = {"ielts_required": True, "ielts_minimum_score": 6.5}
    result = check_ielts(profile, req)
    assert result.status == MatchStatus.DOES_NOT_MEET


def test_ielts_not_required():
    profile = {"ielts_score": None}
    req = {"ielts_required": False}
    result = check_ielts(profile, req)
    assert result.status == MatchStatus.MEETS


def test_ielts_unknown_status():
    profile = {"ielts_score": 7.0}
    req = {"ielts_required": None}
    result = check_ielts(profile, req)
    assert result.status == MatchStatus.UNKNOWN


# ---------- TOEFL ----------

def test_toefl_meets():
    profile = {"toefl_score": 100}
    req = {"toefl_required": True, "toefl_minimum_score": 79}
    result = check_toefl(profile, req)
    assert result.status == MatchStatus.MEETS


# ---------- GRE ----------

def test_gre_required_reports_unknown():
    profile = {}
    req = {"gre_required": True}
    result = check_gre(profile, req)
    assert result.status == MatchStatus.UNKNOWN


def test_gre_not_required_meets():
    profile = {}
    req = {"gre_required": False}
    result = check_gre(profile, req)
    assert result.status == MatchStatus.MEETS


# ---------- Aggregate ----------

def test_overall_meets_when_all_meet():
    profile = {
        "cgpa": 3.5, "cgpa_scale": 4.0,
        "degree_level": "Master",
        "previous_degree": "BSc Computer Science",
        "previous_field": "Computer Science",
        "ielts_score": 7.0,
        "toefl_score": 100,
    }
    req = {
        "minimum_cgpa": 3.0, "minimum_cgpa_scale": 4.0,
        "required_field": "Computer Science",
        "ielts_required": True, "ielts_minimum_score": 6.5,
        "toefl_required": True, "toefl_minimum_score": 79,
        "gre_required": False,
        "verification_status": "verified",
    }
    programme = {"id": 1, "programme_name": "MSc CS"}
    result = match_programme(profile, programme, req)
    assert result.overall_status == MatchStatus.MEETS


def test_overall_becomes_requires_verification_when_unverified():
    """Even if all requirements are MEETS, an unverified record downgrades."""
    profile = {
        "cgpa": 3.5, "cgpa_scale": 4.0,
        "degree_level": "Master",
        "previous_degree": "BSc Computer Science",
        "previous_field": "Computer Science",
    }
    req = {
        "minimum_cgpa": 3.0, "minimum_cgpa_scale": 4.0,
        "required_field": "Computer Science",
        "ielts_required": False,
        "toefl_required": False,
        "gre_required": False,
        "verification_status": "unverified",
    }
    programme = {"id": 1, "programme_name": "MSc CS"}
    result = match_programme(profile, programme, req)
    assert result.overall_status == MatchStatus.REQUIRES_VERIFICATION


def test_overall_does_not_meet_beats_unknown():
    profile = {"cgpa": 2.0, "cgpa_scale": 4.0, "degree_level": "Master", "previous_degree": "BSc CS"}
    req = {"minimum_cgpa": 3.0, "minimum_cgpa_scale": 4.0, "verification_status": "unverified"}
    programme = {"id": 1, "programme_name": "MSc CS"}
    result = match_programme(profile, programme, req)
    # DOES_NOT_MEET wins over REQUIRES_VERIFICATION per our priority order.
    assert result.overall_status == MatchStatus.DOES_NOT_MEET
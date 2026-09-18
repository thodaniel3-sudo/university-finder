"""
Matching engine.

Compares a student profile against a programme's documented admission
requirements and produces a structured result.

This module is PURE — no database access, no Flask, no side effects.
It takes dicts in and returns dataclasses out. That makes it:
  - testable without mocking anything
  - reusable from scripts (e.g. bulk preview tools)
  - safe to call anywhere

Design principle: never say MEETS when we can't be sure.
When in doubt, return UNKNOWN.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MatchStatus(str, Enum):
    """The four possible outcomes for a single requirement."""
    MEETS = "MEETS"
    DOES_NOT_MEET = "DOES_NOT_MEET"
    UNKNOWN = "UNKNOWN"
    REQUIRES_VERIFICATION = "REQUIRES_VERIFICATION"


# Human-readable labels for the UI.
STATUS_LABELS = {
    MatchStatus.MEETS: "Meets documented requirement",
    MatchStatus.DOES_NOT_MEET: "Does not appear to meet documented requirement",
    MatchStatus.UNKNOWN: "Unknown / insufficient data",
    MatchStatus.REQUIRES_VERIFICATION: "Requires manual verification",
}

# Bootstrap 5 color classes for badges.
STATUS_COLORS = {
    MatchStatus.MEETS: "success",
    MatchStatus.DOES_NOT_MEET: "danger",
    MatchStatus.UNKNOWN: "secondary",
    MatchStatus.REQUIRES_VERIFICATION: "warning",
}


@dataclass
class RequirementMatch:
    """Result of comparing one requirement."""
    name: str                                  # e.g. "CGPA"
    status: MatchStatus
    reason: str                                # user-facing explanation
    student_value: Any = None
    required_value: Any = None

    @property
    def label(self) -> str:
        return STATUS_LABELS[self.status]

    @property
    def color(self) -> str:
        return STATUS_COLORS[self.status]


@dataclass
class ProgrammeMatch:
    """Aggregate result for a whole programme."""
    programme_id: int
    programme_name: str
    requirements: list[RequirementMatch] = field(default_factory=list)

    @property
    def overall_status(self) -> MatchStatus:
        """
        Determine the overall picture across all requirements.

        Rules (deliberately conservative):
          - If ANY requirement DOES_NOT_MEET -> overall is DOES_NOT_MEET.
          - Else if ANY is REQUIRES_VERIFICATION -> overall is REQUIRES_VERIFICATION.
          - Else if ANY is UNKNOWN -> overall is UNKNOWN.
          - Else (all MEETS) -> overall is MEETS.
        """
        statuses = {r.status for r in self.requirements}
        if MatchStatus.DOES_NOT_MEET in statuses:
            return MatchStatus.DOES_NOT_MEET
        if MatchStatus.REQUIRES_VERIFICATION in statuses:
            return MatchStatus.REQUIRES_VERIFICATION
        if MatchStatus.UNKNOWN in statuses:
            return MatchStatus.UNKNOWN
        return MatchStatus.MEETS

    @property
    def meets_count(self) -> int:
        return sum(1 for r in self.requirements if r.status == MatchStatus.MEETS)

    @property
    def total_count(self) -> int:
        return len(self.requirements)


# ============================================================
# Helpers
# ============================================================

def _normalise_cgpa(cgpa: float, scale: float, target_scale: float = 4.0) -> float | None:
    """
    Convert CGPA from one scale to another.

    Returns None if scale is invalid (zero, negative, or missing).
    """
    try:
        cgpa = float(cgpa)
        scale = float(scale)
        target_scale = float(target_scale)
    except (TypeError, ValueError):
        return None
    if scale <= 0 or cgpa < 0 or cgpa > scale:
        return None
    return round(cgpa / scale * target_scale, 2)


def _field_matches(student_field: str | None, required_field: str | None) -> bool:
    """
    Loose field comparison — case-insensitive, checks for any word overlap.

    Example: 'Computer Science' matches 'Computer Science or related'
             because 'computer' and 'science' both appear.
    """
    if not student_field or not required_field:
        return False
    student_words = set(student_field.lower().split())
    required_words = set(required_field.lower().split())
    # Remove common stop words that would cause false positives.
    stop = {"or", "and", "related", "field", "the", "a", "an", "in", "of"}
    student_words -= stop
    required_words -= stop
    return bool(student_words & required_words)


# ============================================================
# Individual requirement checks
# ============================================================

def check_cgpa(profile: dict, req: dict) -> RequirementMatch:
    """
    Compare student CGPA against the programme's documented minimum.

    Requires both sides to have CGPA + scale to be comparable.
    If either side is missing, or the scales cannot be reconciled,
    returns UNKNOWN rather than guessing.
    """
    student_cgpa = profile.get("cgpa")
    student_scale = profile.get("cgpa_scale")
    required_cgpa = req.get("minimum_cgpa")
    required_scale = req.get("minimum_cgpa_scale")

    if required_cgpa is None or required_scale is None:
        return RequirementMatch(
            name="CGPA",
            status=MatchStatus.UNKNOWN,
            reason="The university has not published a minimum CGPA for this programme.",
            student_value=student_cgpa,
            required_value=None,
        )

    if student_cgpa is None or student_scale is None:
        return RequirementMatch(
            name="CGPA",
            status=MatchStatus.UNKNOWN,
            reason="Add your CGPA and CGPA scale to your profile to compare.",
            student_value=None,
            required_value=f"{required_cgpa}/{required_scale}",
        )

    # Normalise both to a 4.0 scale for comparison.
    student_norm = _normalise_cgpa(student_cgpa, student_scale)
    required_norm = _normalise_cgpa(required_cgpa, required_scale)
    if student_norm is None or required_norm is None:
        return RequirementMatch(
            name="CGPA",
            status=MatchStatus.UNKNOWN,
            reason=(
                f"Cannot compare CGPA values across scales: "
                f"{student_cgpa}/{student_scale} vs {required_cgpa}/{required_scale}."
            ),
            student_value=f"{student_cgpa}/{student_scale}",
            required_value=f"{required_cgpa}/{required_scale}",
        )

    if student_norm >= required_norm:
        return RequirementMatch(
            name="CGPA",
            status=MatchStatus.MEETS,
            reason=(
                f"Your CGPA {student_cgpa}/{student_scale} "
                f"(≈ {student_norm}/4.0) meets the documented minimum "
                f"{required_cgpa}/{required_scale} (≈ {required_norm}/4.0)."
            ),
            student_value=f"{student_cgpa}/{student_scale}",
            required_value=f"{required_cgpa}/{required_scale}",
        )

    return RequirementMatch(
        name="CGPA",
        status=MatchStatus.DOES_NOT_MEET,
        reason=(
            f"Your CGPA {student_cgpa}/{student_scale} "
            f"(≈ {student_norm}/4.0) is below the documented minimum "
            f"{required_cgpa}/{required_scale} (≈ {required_norm}/4.0)."
        ),
        student_value=f"{student_cgpa}/{student_scale}",
        required_value=f"{required_cgpa}/{required_scale}",
    )


def check_degree_level(profile: dict, req: dict) -> RequirementMatch:
    """
    Check that the student's previous degree qualifies them for the programme level.

    Simple rule: a Master's programme requires at least a Bachelor's.
    PhD requires at least a Master's.
    """
    applying_for = (profile.get("degree_level") or "").strip()
    previous = (profile.get("previous_degree") or "").strip().lower()

    if not applying_for:
        return RequirementMatch(
            name="Degree level",
            status=MatchStatus.UNKNOWN,
            reason="Add the degree level you are applying for to your profile.",
        )

    if not previous:
        return RequirementMatch(
            name="Degree level",
            status=MatchStatus.UNKNOWN,
            reason="Add your previous degree to your profile.",
        )

    # What minimum prior degree does each target level require?
    required_prior = {
        "Master": {"bsc", "bachelor", "b.eng", "b.a", "ba", "b.sc", "hnd"},
        "PhD": {"msc", "master", "m.sc", "m.a", "mphil"},
        "Bachelor": {"diploma", "certificate", "a-level", "waec", "high school"},
    }.get(applying_for)

    if not required_prior:
        return RequirementMatch(
            name="Degree level",
            status=MatchStatus.UNKNOWN,
            reason=f"No rule for applying-for level: {applying_for}.",
        )

    if any(token in previous for token in required_prior):
        return RequirementMatch(
            name="Degree level",
            status=MatchStatus.MEETS,
            reason=f"Your previous degree ({previous}) satisfies the {applying_for}-level entry.",
            student_value=previous,
            required_value=applying_for,
        )

    return RequirementMatch(
        name="Degree level",
        status=MatchStatus.DOES_NOT_MEET,
        reason=(
            f"A {applying_for}'s programme typically requires a prior degree "
            f"such as {' or '.join(sorted(required_prior))}. "
            f"Your recorded degree is '{previous}'."
        ),
        student_value=previous,
        required_value=applying_for,
    )


def check_field(profile: dict, req: dict) -> RequirementMatch:
    """Check that the student's previous field matches the required field."""
    student_field = profile.get("previous_field")
    required_field = req.get("required_field")

    if not required_field:
        return RequirementMatch(
            name="Required field",
            status=MatchStatus.UNKNOWN,
            reason="The university has not documented a specific required field.",
        )

    if not student_field:
        return RequirementMatch(
            name="Required field",
            status=MatchStatus.UNKNOWN,
            reason="Add your previous field of study to your profile.",
            required_value=required_field,
        )

    if _field_matches(student_field, required_field):
        return RequirementMatch(
            name="Required field",
            status=MatchStatus.MEETS,
            reason=f"Your field '{student_field}' matches the requirement '{required_field}'.",
            student_value=student_field,
            required_value=required_field,
        )

    return RequirementMatch(
        name="Required field",
        status=MatchStatus.DOES_NOT_MEET,
        reason=f"Your field '{student_field}' does not clearly match '{required_field}'.",
        student_value=student_field,
        required_value=required_field,
    )


def check_ielts(profile: dict, req: dict) -> RequirementMatch:
    """Check IELTS requirement."""
    required = req.get("ielts_required")
    min_score = req.get("ielts_minimum_score")

    if required is False:
        return RequirementMatch(
            name="IELTS",
            status=MatchStatus.MEETS,
            reason="The university does not require IELTS for this programme.",
        )
    if required is None:
        return RequirementMatch(
            name="IELTS",
            status=MatchStatus.UNKNOWN,
            reason="The university has not documented whether IELTS is required.",
        )

    student_score = profile.get("ielts_score")
    if student_score is None:
        return RequirementMatch(
            name="IELTS",
            status=MatchStatus.UNKNOWN,
            reason="IELTS is required but you have not recorded a score.",
            required_value=min_score,
        )
    if min_score is None:
        return RequirementMatch(
            name="IELTS",
            status=MatchStatus.UNKNOWN,
            reason="IELTS is required, but the university has not published a minimum score.",
            student_value=student_score,
        )

    try:
        score = float(student_score)
        minimum = float(min_score)
    except (TypeError, ValueError):
        return RequirementMatch(
            name="IELTS",
            status=MatchStatus.UNKNOWN,
            reason="Could not compare IELTS scores.",
            student_value=student_score,
            required_value=min_score,
        )

    if score >= minimum:
        return RequirementMatch(
            name="IELTS",
            status=MatchStatus.MEETS,
            reason=f"Your IELTS {score} meets the required minimum {minimum}.",
            student_value=score,
            required_value=minimum,
        )
    return RequirementMatch(
        name="IELTS",
        status=MatchStatus.DOES_NOT_MEET,
        reason=f"Your IELTS {score} is below the required minimum {minimum}.",
        student_value=score,
        required_value=minimum,
    )


def check_toefl(profile: dict, req: dict) -> RequirementMatch:
    """Check TOEFL requirement. Mirrors IELTS logic."""
    required = req.get("toefl_required")
    min_score = req.get("toefl_minimum_score")

    if required is False:
        return RequirementMatch(
            name="TOEFL",
            status=MatchStatus.MEETS,
            reason="The university does not require TOEFL for this programme.",
        )
    if required is None:
        return RequirementMatch(
            name="TOEFL",
            status=MatchStatus.UNKNOWN,
            reason="The university has not documented whether TOEFL is required.",
        )

    student_score = profile.get("toefl_score")
    if student_score is None:
        return RequirementMatch(
            name="TOEFL",
            status=MatchStatus.UNKNOWN,
            reason="TOEFL is required but you have not recorded a score.",
            required_value=min_score,
        )
    if min_score is None:
        return RequirementMatch(
            name="TOEFL",
            status=MatchStatus.UNKNOWN,
            reason="TOEFL is required, but the university has not published a minimum score.",
            student_value=student_score,
        )

    try:
        score = int(student_score)
        minimum = int(min_score)
    except (TypeError, ValueError):
        return RequirementMatch(
            name="TOEFL",
            status=MatchStatus.UNKNOWN,
            reason="Could not compare TOEFL scores.",
            student_value=student_score,
            required_value=min_score,
        )

    if score >= minimum:
        return RequirementMatch(
            name="TOEFL",
            status=MatchStatus.MEETS,
            reason=f"Your TOEFL {score} meets the required minimum {minimum}.",
            student_value=score,
            required_value=minimum,
        )
    return RequirementMatch(
        name="TOEFL",
        status=MatchStatus.DOES_NOT_MEET,
        reason=f"Your TOEFL {score} is below the required minimum {minimum}.",
        student_value=score,
        required_value=minimum,
    )


def check_gre(profile: dict, req: dict) -> RequirementMatch:
    """Check GRE requirement. We don't store a student GRE score, so we
    only report whether GRE is required."""
    required = req.get("gre_required")
    if required is True:
        return RequirementMatch(
            name="GRE",
            status=MatchStatus.UNKNOWN,
            reason="The university requires GRE. Add your score separately or verify with the university.",
        )
    if required is False:
        return RequirementMatch(
            name="GRE",
            status=MatchStatus.MEETS,
            reason="The university does not require GRE for this programme.",
        )
    return RequirementMatch(
        name="GRE",
        status=MatchStatus.UNKNOWN,
        reason="The university has not documented whether GRE is required.",
    )


# ============================================================
# Top-level entry point
# ============================================================

def match_programme(profile: dict, programme: dict, requirements: dict | None) -> ProgrammeMatch:
    """
    Run all checks for one programme.

    `profile`      — student profile dict (from student_profiles).
    `programme`    — programme dict.
    `requirements` — admission_requirements dict (or None if not recorded).

    Returns a ProgrammeMatch with one RequirementMatch per check.
    """
    result = ProgrammeMatch(
        programme_id=programme.get("id", 0),
        programme_name=programme.get("programme_name", "(unnamed programme)"),
    )

    if requirements is None:
        result.requirements.append(RequirementMatch(
            name="Admission requirements",
            status=MatchStatus.UNKNOWN,
            reason="No admission requirements are recorded for this programme yet.",
        ))
        return result

    # The four data-driven checks.
    checks = [
        check_degree_level(profile, requirements),
        check_field(profile, requirements),
        check_cgpa(profile, requirements),
        check_ielts(profile, requirements),
        check_toefl(profile, requirements),
        check_gre(profile, requirements),
    ]
    result.requirements.extend(checks)

    # If the university's requirements themselves are unverified,
    # every MEETS becomes REQUIRES_VERIFICATION — because we can't
    # trust the data yet.
    verification = requirements.get("verification_status")
    if verification and verification != "verified":
        for r in result.requirements:
            if r.status == MatchStatus.MEETS:
                r.status = MatchStatus.REQUIRES_VERIFICATION
                r.reason = (
                    "You appear to meet this requirement, but the university's "
                    "published requirement has not been independently verified. "
                    + r.reason
                )

    return result
"""Build exactly 100 clinical challenge cases."""

from __future__ import annotations

from app.medical_brain.evaluation.clinical_challenge.case_templates import ALL_CHALLENGE_TEMPLATES
from app.medical_brain.evaluation.clinical_challenge.types import TARGET_TOTAL

CHALLENGE_CASES_100: tuple = tuple(ALL_CHALLENGE_TEMPLATES)

assert len(CHALLENGE_CASES_100) == TARGET_TOTAL, f"Expected {TARGET_TOTAL}, got {len(CHALLENGE_CASES_100)}"

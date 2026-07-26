"""Doctor-level Clinical Challenge — 100 realistic multi-turn conversations."""

from app.medical_brain.evaluation.clinical_challenge.case_bank import CHALLENGE_CASES_100
from app.medical_brain.evaluation.clinical_challenge.types import (
    CHALLENGE_METRICS,
    PASS_THRESHOLD,
    TARGET_TOTAL,
)

__all__ = [
    "CHALLENGE_CASES_100",
    "CHALLENGE_METRICS",
    "PASS_THRESHOLD",
    "TARGET_TOTAL",
]

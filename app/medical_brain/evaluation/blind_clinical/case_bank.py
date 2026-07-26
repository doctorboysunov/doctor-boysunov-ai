"""Blind case bank — 500 unseen cases with overlap verification."""

from __future__ import annotations

from app.medical_brain.evaluation.blind_clinical.case_generator import BLIND_CASES_1000

__all__ = ["BLIND_CASES_1000", "BLIND_CASES_500", "verify_unseen", "load_existing_case_texts"]

BLIND_CASES_500 = BLIND_CASES_1000


def load_existing_case_texts() -> set[str]:
    """Collect patient text from all non-blind evaluation banks."""
    texts: set[str] = set()

    try:
        from app.medical_brain.evaluation.clinical_suite.case_bank import CLINICAL_CASES_500

        for c in CLINICAL_CASES_500:
            texts.add(c.opening_message.strip().lower())
    except ImportError:
        pass

    try:
        from app.medical_brain.evaluation.clinical_challenge.case_bank import CHALLENGE_CASES_100

        for c in CHALLENGE_CASES_100:
            texts.add(c.full_patient_text.strip().lower())
            texts.add(c.opening_message.strip().lower())
    except ImportError:
        pass

    try:
        from app.medical_brain.evaluation.real_world.cases import REAL_WORLD_CASES

        for c in REAL_WORLD_CASES:
            texts.add(c.opening_message.strip().lower())
    except ImportError:
        pass

    return texts


def verify_unseen() -> list[str]:
    """Return blind case IDs whose opener overlaps existing banks."""
    existing = load_existing_case_texts()
    overlaps: list[str] = []
    for case in BLIND_CASES_1000:
        opener = case.opening_message.strip().lower()
        full = case.full_patient_text.strip().lower()
        if opener in existing or full in existing:
            overlaps.append(case.id)
    return overlaps

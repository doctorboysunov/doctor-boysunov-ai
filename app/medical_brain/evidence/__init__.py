"""Evidence-based clinical validation — internal only, never patient-facing."""

from app.medical_brain.evidence.catalog import GUIDELINE_RULES, all_sources
from app.medical_brain.evidence.types import EvidenceReport, GuidelineDisagreement


def validate_case_evidence(*args, **kwargs):
    from app.medical_brain.evidence.validate_case import validate_case_evidence as _fn

    return _fn(*args, **kwargs)


def validate_batch_evidence(*args, **kwargs):
    from app.medical_brain.evidence.validate_case import validate_batch_evidence as _fn

    return _fn(*args, **kwargs)


__all__ = [
    "GUIDELINE_RULES",
    "all_sources",
    "EvidenceReport",
    "GuidelineDisagreement",
    "validate_case_evidence",
    "validate_batch_evidence",
]

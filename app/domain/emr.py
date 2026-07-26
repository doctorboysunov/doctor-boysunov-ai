"""Electronic Medical Record (EMR) domain types."""

from __future__ import annotations

from typing import Literal

EMR_VISIT_FIELDS = (
    "visit_date",
    "main_complaint",
    "examination_findings",
    "neurological_examination",
    "preliminary_diagnosis",
    "final_diagnosis",
    "icd10_code",
    "recommended_examinations",
    "treatment_plan",
    "procedures_performed",
    "follow_up_schedule",
    "notes",
)

TimelineEventType = Literal[
    "visit",
    "follow_up",
    "appointment",
    "medical_record",
    "treatment",
]

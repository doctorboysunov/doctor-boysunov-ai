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

EMR_V1_FIELDS = (
    "ai_assessment_json",
    "ai_review_status",
    "doctor_reviewed_at",
    "doctor_reviewed_by",
    "urgency",
    "primary_specialty",
    "secondary_specialties_json",
)

AiReviewStatus = Literal["none", "draft", "reviewed"]

TimelineEventType = Literal[
    "visit",
    "follow_up",
    "appointment",
    "medical_record",
    "treatment",
    "ai_consultation",
]


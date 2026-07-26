"""EMR AI assessment — structured storage and doctor review workflow."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.repositories.emr_repository import get_emr_visit, list_visits_pending_ai_review, update_emr_visit

logger = logging.getLogger("doctor_boysunov.emr_ai")

ASSESSMENT_VERSION = "1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_ai_assessment(
    visit_id: int,
    *,
    doctor_emr: dict[str, Any],
    medical_brain: dict[str, Any] | None = None,
    primary_specialty: str | None = None,
    secondary_specialties: list[str] | None = None,
    internal_reasoning: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist structured AI assessment on visit — status becomes 'draft'."""
    visit = get_emr_visit(visit_id)
    if visit is None:
        raise ValueError(f"Visit not found: {visit_id}")

    urgency = doctor_emr.get("urgency") or "routine"
    assessment = {
        "version": ASSESSMENT_VERSION,
        "saved_at": _utc_now(),
        "doctor_emr": doctor_emr,
        "medical_brain": medical_brain,
        "internal_reasoning": internal_reasoning,
        "primary_specialty": primary_specialty,
        "secondary_specialties": secondary_specialties or [],
    }

    updated = update_emr_visit(
        visit_id,
        main_complaint=doctor_emr.get("chief_complaint") or visit.get("main_complaint"),
        preliminary_diagnosis=_join_list(doctor_emr.get("differential_diagnoses")),
        recommended_examinations=_join_list(doctor_emr.get("recommended_investigations")),
        urgency=urgency,
        primary_specialty=primary_specialty,
        secondary_specialties_json=json.dumps(secondary_specialties or [], ensure_ascii=False),
        ai_assessment_json=json.dumps(assessment, ensure_ascii=False),
        ai_review_status="draft",
    )
    if updated is None:
        raise ValueError(f"Failed to save AI assessment for visit {visit_id}")

    logger.info("ai_assessment_saved visit_id=%s urgency=%s", visit_id, urgency)
    return updated


def review_visit(
    visit_id: int,
    *,
    doctor_id: str,
    final_diagnosis: str | None = None,
    preliminary_diagnosis: str | None = None,
    treatment_plan: str | None = None,
    examination_findings: str | None = None,
    notes: str | None = None,
    approve: bool = True,
) -> dict[str, Any]:
    """Doctor reviews and signs off AI-generated EMR draft."""
    visit = get_emr_visit(visit_id)
    if visit is None:
        raise ValueError(f"Visit not found: {visit_id}")

    fields: dict[str, Any] = {
        "doctor_reviewed_at": _utc_now(),
        "doctor_reviewed_by": doctor_id,
        "ai_review_status": "reviewed" if approve else "draft",
    }
    if final_diagnosis is not None:
        fields["final_diagnosis"] = final_diagnosis
    if preliminary_diagnosis is not None:
        fields["preliminary_diagnosis"] = preliminary_diagnosis
    if treatment_plan is not None:
        fields["treatment_plan"] = treatment_plan
    if examination_findings is not None:
        fields["examination_findings"] = examination_findings
    if notes is not None:
        fields["notes"] = notes

    updated = update_emr_visit(visit_id, **fields)
    if updated is None:
        raise ValueError(f"Failed to review visit {visit_id}")

    logger.info("visit_reviewed visit_id=%s doctor=%s approved=%s", visit_id, doctor_id, approve)
    return updated


def get_ai_assessment(visit_id: int) -> dict[str, Any] | None:
    visit = get_emr_visit(visit_id)
    if visit is None or not visit.get("ai_assessment_json"):
        return None
    try:
        return json.loads(visit["ai_assessment_json"])
    except json.JSONDecodeError:
        return None


def list_pending_reviews(*, limit: int = 50) -> list[dict[str, Any]]:
    visits = list_visits_pending_ai_review(limit=limit)
    for visit in visits:
        assessment = None
        if visit.get("ai_assessment_json"):
            try:
                assessment = json.loads(visit["ai_assessment_json"])
            except json.JSONDecodeError:
                assessment = None
        visit["ai_assessment"] = assessment
        if visit.get("secondary_specialties_json"):
            try:
                visit["secondary_specialties"] = json.loads(visit["secondary_specialties_json"])
            except json.JSONDecodeError:
                visit["secondary_specialties"] = []
    return visits


def _join_list(items: Any) -> str | None:
    if not items:
        return None
    if isinstance(items, list):
        return "; ".join(str(x) for x in items if str(x).strip())
    return str(items)

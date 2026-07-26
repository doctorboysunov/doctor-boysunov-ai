"""Doctor visit mode — save admin clinical notes to the active patient's EMR."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.repositories.emr_repository import get_emr_visit, list_emr_visits_for_patient
from app.services.appointment_dates import clinic_today_iso
from app.services.doctor_visit_parser import ParsedDoctorVisitNote, parse_doctor_visit_note
from app.services.emr_service import create_visit, edit_visit

logger = logging.getLogger("doctor_boysunov.doctor_visit")

_MERGE_FIELDS = (
    "main_complaint",
    "examination_findings",
    "neurological_examination",
    "preliminary_diagnosis",
    "final_diagnosis",
    "recommended_examinations",
    "treatment_plan",
    "follow_up_schedule",
    "notes",
)


@dataclass(frozen=True)
class DoctorVisitSaveResult:
    patient_id: int
    visit_id: int
    saved_fields: tuple[str, ...]
    parsed: ParsedDoctorVisitNote


def resolve_active_visit_id(patient_id: int, visit_id: int | None = None) -> int:
    if visit_id is not None:
        visit = get_emr_visit(visit_id)
        if visit is not None and visit["patient_id"] == patient_id:
            return visit_id

    visits = list_emr_visits_for_patient(patient_id)
    if visits:
        return int(visits[0]["id"])

    visit = create_visit(patient_id, visit_date=clinic_today_iso())
    return int(visit["id"])


def _merge_field(existing: str | None, new: str | None) -> str | None:
    if not new:
        return existing
    if not existing:
        return new
    if new.strip() in existing:
        return existing
    return f"{existing}\n{new}"


def record_doctor_visit_note(
    patient_id: int,
    text: str,
    *,
    visit_id: int | None = None,
) -> DoctorVisitSaveResult:
    parsed = parse_doctor_visit_note(text)
    if not parsed.has_clinical_content:
        raise ValueError("No clinical content detected")

    active_visit_id = resolve_active_visit_id(patient_id, visit_id=visit_id)
    visit = get_emr_visit(active_visit_id)
    if visit is None:
        raise ValueError(f"Visit not found: {active_visit_id}")

    updates: dict[str, Any] = {}
    parsed_fields = parsed.as_update_fields()
    for field_name in _MERGE_FIELDS:
        if field_name not in parsed_fields:
            continue
        merged = _merge_field(visit.get(field_name), parsed_fields[field_name])
        if merged != visit.get(field_name):
            updates[field_name] = merged

    if not updates:
        return DoctorVisitSaveResult(
            patient_id=patient_id,
            visit_id=active_visit_id,
            saved_fields=(),
            parsed=parsed,
        )

    edit_visit(patient_id, active_visit_id, **updates)
    logger.info(
        "doctor_visit_note_saved patient_id=%s visit_id=%s fields=%s",
        patient_id,
        active_visit_id,
        sorted(updates),
    )
    return DoctorVisitSaveResult(
        patient_id=patient_id,
        visit_id=active_visit_id,
        saved_fields=tuple(sorted(updates)),
        parsed=parsed,
    )


def format_doctor_visit_confirmation(
    *,
    patient_name: str,
    result: DoctorVisitSaveResult,
) -> str:
    field_labels = {
        "main_complaint": "Shikoyat",
        "examination_findings": "Tekshiruv",
        "neurological_examination": "Nevrologik tekshiruv",
        "preliminary_diagnosis": "Tashxis",
        "final_diagnosis": "Yakuniy tashxis",
        "recommended_examinations": "Tavsiya etilgan tekshiruvlar",
        "treatment_plan": "Davolash",
        "follow_up_schedule": "Keyingi ko'rik",
        "notes": "Izoh",
    }
    saved = [field_labels.get(name, name) for name in result.saved_fields]
    saved_text = ", ".join(saved) if saved else "EMR"

    return (
        f"✅ EMR saqlandi — {patient_name}\n"
        f"Visit ID: {result.visit_id}\n"
        f"Maydonlar: {saved_text}\n\n"
        "Keyingi ma'lumotlarni yozing yoki yangi bemor uchun /add_patient buyrug'ini bosing."
    )

"""Electronic Medical Record service — visits, history, and timeline."""

from __future__ import annotations

from typing import Any

from app.repositories.appointment_repository import get_patient_appointments
from app.repositories.emr_repository import (
    count_emr_visits_for_patient,
    create_emr_visit,
    get_emr_visit,
    list_emr_visits_for_patient,
    update_emr_visit,
)
from app.repositories.care_manager_repository import list_care_manager_records_for_patient
from app.repositories.follow_up_repository import list_follow_ups_for_patient
from app.repositories.medical_history_repository import get_medical_history
from app.repositories.patient_intake_repository import get_patient_card
from app.repositories.patient_profile_repository import get_patient_profile
from app.repositories.treatment_repository import list_treatments_for_patient
from app.services.follow_up_planner import on_visit_completed


def _trigger_follow_up_on_visit_complete(patient_id: int, visit: dict[str, Any]) -> None:
    if visit.get("final_diagnosis"):
        on_visit_completed(patient_id=patient_id, visit_date=visit["visit_date"])


def _ensure_patient(patient_id: int) -> dict[str, Any]:
    profile = get_patient_profile(patient_id)
    if profile is None:
        raise ValueError(f"Patient not found: {patient_id}")
    return profile


def create_visit(
    patient_id: int,
    *,
    visit_date: str,
    main_complaint: str | None = None,
    examination_findings: str | None = None,
    neurological_examination: str | None = None,
    preliminary_diagnosis: str | None = None,
    final_diagnosis: str | None = None,
    icd10_code: str | None = None,
    recommended_examinations: str | None = None,
    treatment_plan: str | None = None,
    procedures_performed: str | None = None,
    follow_up_schedule: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    _ensure_patient(patient_id)
    visit = create_emr_visit(
        patient_id,
        visit_date=visit_date,
        main_complaint=main_complaint,
        examination_findings=examination_findings,
        neurological_examination=neurological_examination,
        preliminary_diagnosis=preliminary_diagnosis,
        final_diagnosis=final_diagnosis,
        icd10_code=icd10_code,
        recommended_examinations=recommended_examinations,
        treatment_plan=treatment_plan,
        procedures_performed=procedures_performed,
        follow_up_schedule=follow_up_schedule,
        notes=notes,
    )
    _trigger_follow_up_on_visit_complete(patient_id, visit)
    return visit


def edit_visit(
    patient_id: int,
    visit_id: int,
    **fields: str | None,
) -> dict[str, Any]:
    visit = get_emr_visit(visit_id)
    if visit is None or visit["patient_id"] != patient_id:
        raise ValueError(f"Visit not found: {visit_id}")

    had_final_diagnosis = bool(visit.get("final_diagnosis"))

    updated = update_emr_visit(visit_id, **fields)
    if updated is None:
        raise ValueError(f"Visit not found: {visit_id}")

    if updated.get("final_diagnosis") and not had_final_diagnosis:
        _trigger_follow_up_on_visit_complete(patient_id, updated)
    return updated


def get_visit_history(patient_id: int) -> dict[str, Any]:
    _ensure_patient(patient_id)
    visits = list_emr_visits_for_patient(patient_id)
    return {
        "patient_id": patient_id,
        "visit_count": len(visits),
        "visits": visits,
        "previous_complaints": [
            {"visit_id": v["id"], "visit_date": v["visit_date"], "complaint": v["main_complaint"]}
            for v in visits
            if v.get("main_complaint")
        ],
        "previous_diagnoses": _collect_diagnoses(visits),
        "previous_treatments": [
            {
                "visit_id": v["id"],
                "visit_date": v["visit_date"],
                "treatment_plan": v["treatment_plan"],
                "procedures_performed": v["procedures_performed"],
            }
            for v in visits
            if v.get("treatment_plan") or v.get("procedures_performed")
        ],
        "previous_follow_ups": list_follow_ups_for_patient(patient_id),
    }


def _collect_diagnoses(visits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnoses: list[dict[str, Any]] = []
    for visit in visits:
        if visit.get("preliminary_diagnosis"):
            diagnoses.append(
                {
                    "visit_id": visit["id"],
                    "visit_date": visit["visit_date"],
                    "kind": "preliminary",
                    "diagnosis": visit["preliminary_diagnosis"],
                    "icd10_code": visit.get("icd10_code"),
                }
            )
        if visit.get("final_diagnosis"):
            diagnoses.append(
                {
                    "visit_id": visit["id"],
                    "visit_date": visit["visit_date"],
                    "kind": "final",
                    "diagnosis": visit["final_diagnosis"],
                    "icd10_code": visit.get("icd10_code"),
                }
            )
    return diagnoses


def build_patient_timeline(patient_id: int) -> dict[str, Any]:
    _ensure_patient(patient_id)
    events: list[dict[str, Any]] = []

    for visit in list_emr_visits_for_patient(patient_id):
        title = visit.get("main_complaint") or "Clinical visit"
        summary_parts = [
            part
            for part in (
                visit.get("final_diagnosis") or visit.get("preliminary_diagnosis"),
                visit.get("treatment_plan"),
            )
            if part
        ]
        events.append(
            {
                "event_type": "visit",
                "event_date": visit["visit_date"],
                "sort_key": f"{visit['visit_date']}T23:59:59#{visit['id']:08d}",
                "title": title,
                "summary": " — ".join(summary_parts) if summary_parts else None,
                "visit_id": visit["id"],
                "data": visit,
            }
        )

    for follow_up in list_follow_ups_for_patient(patient_id):
        events.append(
            {
                "event_type": "follow_up",
                "event_date": follow_up["scheduled_date"],
                "sort_key": f"{follow_up['scheduled_date']}T12:00:00#f{follow_up['id']:08d}",
                "title": f"Follow-up #{follow_up['sequence_number']}",
                "summary": follow_up.get("invitation_text"),
                "follow_up_id": follow_up["id"],
                "data": follow_up,
            }
        )

    for appointment in get_patient_appointments(patient_id):
        events.append(
            {
                "event_type": "appointment",
                "event_date": appointment["appointment_date"],
                "sort_key": f"{appointment['appointment_date']}T{appointment['appointment_time']}#a{appointment['id']:08d}",
                "title": appointment.get("complaint") or "Appointment",
                "summary": f"{appointment.get('doctor_name')} — {appointment.get('status')}",
                "appointment_id": appointment["id"],
                "data": appointment,
            }
        )

    for record in get_medical_history(patient_id):
        event_date = record.get("event_date") or record["created_at"][:10]
        events.append(
            {
                "event_type": "medical_record",
                "event_date": event_date,
                "sort_key": f"{event_date}T00:00:00#m{record['id']:08d}",
                "title": record["record_type"].replace("_", " ").title(),
                "summary": record["content"][:200],
                "medical_record_id": record["id"],
                "data": record,
            }
        )

    for record in list_care_manager_records_for_patient(patient_id):
        events.append(
            {
                "event_type": "care_manager",
                "event_date": record["event_date"],
                "sort_key": f"{record['event_date']}T12:00:00#c{record['id']:08d}",
                "title": record["event_type"].replace("_", " ").title(),
                "summary": record.get("reply_text") or record.get("message_text"),
                "outcome": record.get("outcome"),
                "care_manager_record_id": record["id"],
                "data": record,
            }
        )

    for treatment in list_treatments_for_patient(patient_id):
        started = treatment["started_at"][:10]
        events.append(
            {
                "event_type": "treatment",
                "event_date": started,
                "sort_key": f"{started}T00:00:01#t{treatment['id']:08d}",
                "title": f"Treatment started ({treatment['status']})",
                "summary": None,
                "treatment_id": treatment["id"],
                "data": treatment,
            }
        )

    events.sort(key=lambda item: item["sort_key"], reverse=True)
    for event in events:
        event.pop("sort_key", None)

    return {
        "patient_id": patient_id,
        "event_count": len(events),
        "timeline": events,
    }


def build_patient_emr(patient_id: int) -> dict[str, Any]:
    card = get_patient_card(patient_id)
    if card is None:
        raise ValueError(f"Patient not found: {patient_id}")

    history = get_visit_history(patient_id)
    timeline = build_patient_timeline(patient_id)

    return {
        **card,
        "emr": {
            "visit_count": count_emr_visits_for_patient(patient_id),
            "visits": history["visits"],
            "previous_complaints": history["previous_complaints"],
            "previous_diagnoses": history["previous_diagnoses"],
            "previous_treatments": history["previous_treatments"],
            "previous_follow_ups": history["previous_follow_ups"],
            "care_manager_records": list_care_manager_records_for_patient(patient_id),
            "timeline": timeline["timeline"],
        },
    }


def ensure_initial_visit_on_registration(
    *,
    patient_id: int,
    full_name: str,
    phone_number: str,
    visit_date: str,
    follow_up_dates: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    """Create the first EMR visit when a patient is registered (skip if visits exist)."""
    if count_emr_visits_for_patient(patient_id) > 0:
        return None

    schedule_text = ", ".join(follow_up_dates[:7]) if follow_up_dates else None
    return create_emr_visit(
        patient_id,
        visit_date=visit_date,
        main_complaint=None,
        notes=f"Initial registration: {full_name}, phone {phone_number}",
        follow_up_schedule=schedule_text,
    )

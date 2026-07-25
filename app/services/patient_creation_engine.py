"""Intelligent patient creation — full profile, records, and follow-ups from name + phone."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.repositories.follow_up_repository import list_follow_ups_for_patient
from app.repositories.medical_history_repository import add_medical_record
from app.repositories.patient_intake_repository import find_patient_by_phone, search_patients
from app.repositories.treatment_repository import get_active_treatment
from app.services.appointment_dates import clinic_today_iso
from app.services.follow_up_planner import start_patient_follow_up_schedule
from app.services.patient_intake.service import capture_patient

logger = logging.getLogger("doctor_boysunov.patient_creation")


@dataclass(frozen=True)
class PatientCreationResult:
    patient_id: int
    full_name: str
    phone_number: str
    created: bool
    source: str
    treatment_id: int | None
    treatment_started: bool
    medical_record_id: int | None
    follow_up_count: int
    follow_up_dates: tuple[str, ...]
    duplicate_prevented: bool


def _ensure_treatment_and_records(
    *,
    patient_id: int,
    full_name: str,
    phone_number: str,
    started_at: str,
) -> tuple[int, int, int, tuple[str, ...]]:
    active = get_active_treatment(patient_id)
    if active is not None:
        follow_ups = list_follow_ups_for_patient(patient_id)
        dates = tuple(item["scheduled_date"] for item in follow_ups)
        return int(active["id"]), 0, len(follow_ups), dates

    record = add_medical_record(
        patient_id,
        "consultation",
        f"Bemor ro'yxatdan o'tkazildi: {full_name}",
        notes=f"Telefon: {phone_number}",
        event_date=started_at,
    )
    treatment = start_patient_follow_up_schedule(
        patient_id=patient_id,
        started_at=started_at,
    )
    follow_ups = list_follow_ups_for_patient(patient_id)
    dates = tuple(item["scheduled_date"] for item in follow_ups)
    return int(treatment["id"]), int(record["id"]), len(follow_ups), dates


def create_patient_intelligently(
    *,
    source: str,
    started_at: str | None = None,
    text: str | None = None,
    full_name: str | None = None,
    phone_number: str | None = None,
    audio_bytes: bytes | None = None,
    image_bytes: bytes | None = None,
    image_mime_type: str = "image/jpeg",
    telegram_id: int | None = None,
    username: str | None = None,
) -> PatientCreationResult | None:
    """Create or locate a patient and ensure treatment timeline + follow-ups exist."""
    capture = capture_patient(
        source=source,
        text=text,
        full_name=full_name,
        phone_number=phone_number,
        audio_bytes=audio_bytes,
        image_bytes=image_bytes,
        image_mime_type=image_mime_type,
        telegram_id=telegram_id,
        username=username,
    )
    if capture is None:
        return None

    treatment_start = started_at or clinic_today_iso()
    had_active = get_active_treatment(capture.patient_id) is not None

    treatment_id, medical_record_id, follow_up_count, follow_up_dates = (
        _ensure_treatment_and_records(
            patient_id=capture.patient_id,
            full_name=capture.full_name,
            phone_number=capture.phone_number,
            started_at=treatment_start,
        )
    )

    result = PatientCreationResult(
        patient_id=capture.patient_id,
        full_name=capture.full_name,
        phone_number=capture.phone_number,
        created=capture.created,
        source=capture.source,
        treatment_id=treatment_id,
        treatment_started=not had_active,
        medical_record_id=medical_record_id or None,
        follow_up_count=follow_up_count,
        follow_up_dates=follow_up_dates,
        duplicate_prevented=not capture.created,
    )
    logger.info(
        "patient_created_intelligently patient_id=%s created=%s treatment_started=%s follow_ups=%s",
        result.patient_id,
        result.created,
        result.treatment_started,
        result.follow_up_count,
    )
    return result


def format_creation_summary(result: PatientCreationResult) -> str:
    if result.created:
        headline = "Bemor muvaffaqiyatli yaratildi."
    elif result.duplicate_prevented:
        headline = "Bemor allaqachon mavjud (telefon bo'yicha)."
    else:
        headline = "Bemor topildi."

    lines = [
        headline,
        "",
        f"Patient ID: {result.patient_id}",
        f"Ism: {result.full_name}",
        f"Telefon: {result.phone_number}",
        f"Manba: {result.source}",
    ]

    if result.treatment_id is not None:
        lines.append(f"Davolanish ID: {result.treatment_id}")

    if result.treatment_started:
        lines.append("Davolanish va kuzatuv jadvali yaratildi.")
    elif result.treatment_id is not None:
        lines.append("Faol davolanish allaqachon mavjud.")

    if result.medical_record_id is not None:
        lines.append(f"Tibbiy yozuv ID: {result.medical_record_id}")

    if result.follow_up_count:
        lines.append(f"Kuzatuvlar: {result.follow_up_count} ta rejalashtirildi")
        preview = result.follow_up_dates[:5]
        if preview:
            lines.append("Birinchi sanalar: " + ", ".join(preview))

    if find_patient_by_phone(result.phone_number) is not None:
        lines.append("\nQidiruv: telefon bo'yicha topiladi.")

    return "\n".join(lines)


def format_admin_creation_confirmation(result: PatientCreationResult) -> str:
    """Short confirmation for doctor/admin mode — no consultation prompts."""
    if result.created:
        headline = "✅ Patient created"
    elif result.duplicate_prevented:
        headline = "ℹ️ Patient already exists"
    else:
        headline = "ℹ️ Patient found"

    lines = [
        headline,
        f"👤 {result.full_name}",
        f"📱 {result.phone_number}",
        f"🆔 Patient ID: {result.patient_id}",
    ]
    if result.follow_up_count:
        lines.append("📅 Follow-ups scheduled")
    return "\n".join(lines)

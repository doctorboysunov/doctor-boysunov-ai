"""Universal patient capture entry point for Telegram, Web, and Mobile."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.repositories.medical_history_repository import add_medical_record
from app.repositories.patient_intake_repository import (
    create_captured_patient,
    find_patient_by_phone,
    get_capture_record,
)
from app.services.patient_intake.clinical_form import (
    ClinicalFormData,
    extract_clinical_form,
    is_clinical_form_text,
)
from app.services.patient_intake.extraction import (
    ExtractedPatient,
    extract_patient_from_text,
    extract_patient_with_ai,
)
from app.services.patient_intake.ocr import extract_patient_from_image
from app.services.patient_intake.transcribe import transcribe_audio

logger = logging.getLogger("doctor_boysunov.patient_intake")


@dataclass(frozen=True)
class CaptureResult:
    patient_id: int
    full_name: str
    phone_number: str
    created: bool
    source: str


@dataclass(frozen=True)
class ClinicalCaptureResult:
    patient_id: int
    full_name: str
    phone_number: str
    created: bool
    source: str
    diagnosis: str | None = None
    complaint: str | None = None
    treatment: str | None = None
    next_follow_up: str | None = None
    records_saved: int = 0


def _save_or_return_existing(
    extracted: ExtractedPatient,
    *,
    source: str,
    telegram_id: int | None = None,
    username: str | None = None,
) -> CaptureResult:
    existing = find_patient_by_phone(extracted.phone_number)
    if existing is not None:
        patient_id = int(existing["user_id"])
        if not existing.get("full_name"):
            from app.repositories.patient_profile_repository import update_patient_profile

            update_patient_profile(patient_id, full_name=extracted.full_name)
        record = get_capture_record(patient_id)
        return CaptureResult(
            patient_id=patient_id,
            full_name=record["full_name"] or extracted.full_name,
            phone_number=record["phone_number"] or extracted.phone_number,
            created=False,
            source=source,
        )

    profile = create_captured_patient(
        full_name=extracted.full_name,
        phone_number=extracted.phone_number,
        source=source,
        telegram_id=telegram_id,
        username=username,
    )
    return CaptureResult(
        patient_id=int(profile["user_id"]),
        full_name=profile["full_name"] or extracted.full_name,
        phone_number=profile["phone_number"] or extracted.phone_number,
        created=True,
        source=source,
    )


def _save_clinical_records(patient_id: int, form: ClinicalFormData) -> int:
    saved = 0
    if form.complaint:
        add_medical_record(patient_id, "symptom", form.complaint)
        saved += 1
    if form.diagnosis:
        add_medical_record(patient_id, "diagnosis", form.diagnosis)
        saved += 1
    if form.treatment:
        notes = None
        if form.next_follow_up:
            notes = f"Keyingi kuzatuv: {form.next_follow_up}"
        add_medical_record(patient_id, "treatment", form.treatment, notes=notes)
        saved += 1
    elif form.next_follow_up:
        add_medical_record(
            patient_id,
            "consultation",
            f"Keyingi kuzatuv: {form.next_follow_up}",
        )
        saved += 1
    return saved


def capture_clinical_form(
    text: str,
    *,
    source: str,
    telegram_id: int | None = None,
    username: str | None = None,
) -> ClinicalCaptureResult | None:
    form = extract_clinical_form(text)
    if form is None:
        return None

    capture = _save_or_return_existing(
        ExtractedPatient(full_name=form.full_name, phone_number=form.phone_number),
        source=source,
        telegram_id=telegram_id,
        username=username,
    )
    records_saved = _save_clinical_records(capture.patient_id, form)

    return ClinicalCaptureResult(
        patient_id=capture.patient_id,
        full_name=capture.full_name,
        phone_number=capture.phone_number,
        created=capture.created,
        source=capture.source,
        diagnosis=form.diagnosis,
        complaint=form.complaint,
        treatment=form.treatment,
        next_follow_up=form.next_follow_up,
        records_saved=records_saved,
    )


def capture_patient_from_text(
    text: str,
    *,
    source: str,
    telegram_id: int | None = None,
    username: str | None = None,
    use_ai: bool = False,
) -> CaptureResult | None:
    extracted = extract_patient_with_ai(text) if use_ai else extract_patient_from_text(text)
    if extracted is None:
        return None
    return _save_or_return_existing(
        extracted,
        source=source,
        telegram_id=telegram_id,
        username=username,
    )


def capture_patient_from_voice(
    audio_bytes: bytes,
    *,
    source: str = "voice",
    telegram_id: int | None = None,
    username: str | None = None,
) -> CaptureResult | None:
    transcript = transcribe_audio(audio_bytes)
    logger.info("voice_transcript=%r", transcript)
    extracted = extract_patient_from_text(transcript)
    if extracted is None:
        extracted = extract_patient_with_ai(transcript)
    if extracted is None:
        logger.warning("voice_extraction_failed transcript=%r", transcript)
        return None
    logger.info(
        "voice_extracted name=%r phone=%r",
        extracted.full_name,
        extracted.phone_number,
    )
    return _save_or_return_existing(
        extracted,
        source=source,
        telegram_id=telegram_id,
        username=username,
    )


def capture_patient_from_image(
    image_bytes: bytes,
    *,
    source: str = "ocr",
    mime_type: str = "image/jpeg",
    telegram_id: int | None = None,
    username: str | None = None,
) -> CaptureResult | None:
    extracted = extract_patient_from_image(image_bytes, mime_type=mime_type)
    if extracted is None:
        return None
    return _save_or_return_existing(
        extracted,
        source=source,
        telegram_id=telegram_id,
        username=username,
    )


def capture_patient_from_contact(
    *,
    full_name: str,
    phone_number: str,
    source: str = "contact",
    telegram_id: int | None = None,
    username: str | None = None,
) -> CaptureResult:
    extracted = ExtractedPatient(full_name=full_name.strip(), phone_number=phone_number)
    return _save_or_return_existing(
        extracted,
        source=source,
        telegram_id=telegram_id,
        username=username,
    )


def capture_patient(
    *,
    source: str,
    text: str | None = None,
    full_name: str | None = None,
    phone_number: str | None = None,
    audio_bytes: bytes | None = None,
    image_bytes: bytes | None = None,
    image_mime_type: str = "image/jpeg",
    telegram_id: int | None = None,
    username: str | None = None,
) -> CaptureResult | None:
    if audio_bytes is not None:
        return capture_patient_from_voice(
            audio_bytes,
            source=source if source in {"voice", "mobile", "web"} else "voice",
            telegram_id=telegram_id,
            username=username,
        )
    if image_bytes is not None:
        return capture_patient_from_image(
            image_bytes,
            source=source if source in {"ocr", "mobile", "web"} else "ocr",
            mime_type=image_mime_type,
            telegram_id=telegram_id,
            username=username,
        )
    if full_name and phone_number:
        return capture_patient_from_contact(
            full_name=full_name,
            phone_number=phone_number,
            source=source if source in {"contact", "mobile", "web"} else "contact",
            telegram_id=telegram_id,
            username=username,
        )
    if text:
        return capture_patient_from_text(
            text,
            source=source,
            telegram_id=telegram_id,
            username=username,
            use_ai=source in {"voice", "ocr", "mobile", "web"},
        )
    return None

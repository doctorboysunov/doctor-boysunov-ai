"""Web and Mobile patient capture API."""

from __future__ import annotations

import base64
import binascii

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import PATIENT_INTAKE_API_KEY
from app.db.connection import init_db
from app.services.patient_creation_engine import (
    PatientCreationResult,
    create_patient_intelligently,
)
from app.services.patient_intake.service import (
    ClinicalCaptureResult,
    CaptureResult,
    capture_clinical_form,
    capture_patient,
)

app = FastAPI(title="Doctor Boysunov Patient Intake API", version="1.0.0")


class CaptureRequest(BaseModel):
    source: str = Field(..., pattern="^(web|mobile)$")
    text: str | None = None
    full_name: str | None = None
    phone_number: str | None = None
    audio_base64: str | None = None
    image_base64: str | None = None
    image_mime_type: str = "image/jpeg"


class CaptureResponse(BaseModel):
    patient_id: int
    full_name: str
    phone_number: str
    created: bool
    source: str
    treatment_id: int | None = None
    treatment_started: bool = False
    medical_record_id: int | None = None
    follow_up_count: int = 0
    follow_up_dates: list[str] = Field(default_factory=list)
    duplicate_prevented: bool = False


class PatientSearchResponse(BaseModel):
    patients: list[CaptureResponse]


def _creation_to_response(result: PatientCreationResult) -> CaptureResponse:
    return CaptureResponse(
        patient_id=result.patient_id,
        full_name=result.full_name,
        phone_number=result.phone_number,
        created=result.created,
        source=result.source,
        treatment_id=result.treatment_id,
        treatment_started=result.treatment_started,
        medical_record_id=result.medical_record_id,
        follow_up_count=result.follow_up_count,
        follow_up_dates=list(result.follow_up_dates),
        duplicate_prevented=result.duplicate_prevented,
    )


def _decode_base64(value: str, *, label: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {label} base64") from exc


def _verify_api_key(api_key: str | None) -> None:
    if not PATIENT_INTAKE_API_KEY:
        return
    if api_key != PATIENT_INTAKE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class ClinicalCaptureResponse(CaptureResponse):
    diagnosis: str | None = None
    complaint: str | None = None
    treatment: str | None = None
    next_follow_up: str | None = None
    records_saved: int = 0


class ClinicalFormRequest(BaseModel):
    source: str = Field(..., pattern="^(web|mobile|telegram)$")
    text: str = Field(..., min_length=1)


@app.post("/api/v1/patients/clinical-form", response_model=ClinicalCaptureResponse)
def capture_clinical_form_api(
    payload: ClinicalFormRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> ClinicalCaptureResponse:
    _verify_api_key(x_api_key)

    result = capture_clinical_form(payload.text, source=payload.source)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail="Could not parse clinical form (Ism, Familiya, Telefon required)",
        )

    return ClinicalCaptureResponse(
        patient_id=result.patient_id,
        full_name=result.full_name,
        phone_number=result.phone_number,
        created=result.created,
        source=result.source,
        diagnosis=result.diagnosis,
        complaint=result.complaint,
        treatment=result.treatment,
        next_follow_up=result.next_follow_up,
        records_saved=result.records_saved,
    )


@app.post("/api/v1/patients/create", response_model=CaptureResponse)
def create_patient_api(
    payload: CaptureRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> CaptureResponse:
    """Phase 6.5: intelligent patient creation with treatment timeline and follow-ups."""
    _verify_api_key(x_api_key)

    audio_bytes = (
        _decode_base64(payload.audio_base64, label="audio")
        if payload.audio_base64
        else None
    )
    image_bytes = (
        _decode_base64(payload.image_base64, label="image")
        if payload.image_base64
        else None
    )

    result = create_patient_intelligently(
        source=payload.source,
        text=payload.text,
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        audio_bytes=audio_bytes,
        image_bytes=image_bytes,
        image_mime_type=payload.image_mime_type,
    )
    if result is None:
        raise HTTPException(
            status_code=422,
            detail="Could not extract full_name and phone_number from input",
        )

    return _creation_to_response(result)


@app.get("/api/v1/patients/search", response_model=PatientSearchResponse)
def search_patients_api(
    q: str,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> PatientSearchResponse:
    _verify_api_key(x_api_key)

    from app.repositories.patient_intake_repository import search_patients

    profiles = search_patients(q)
    patients = [
        CaptureResponse(
            patient_id=int(profile["user_id"]),
            full_name=profile.get("full_name") or "",
            phone_number=profile.get("phone_number") or "",
            created=False,
            source="search",
        )
        for profile in profiles
    ]
    return PatientSearchResponse(patients=patients)


@app.post("/api/v1/patients/capture", response_model=CaptureResponse)
def capture_patient_api(
    payload: CaptureRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> CaptureResponse:
    _verify_api_key(x_api_key)

    audio_bytes = (
        _decode_base64(payload.audio_base64, label="audio")
        if payload.audio_base64
        else None
    )
    image_bytes = (
        _decode_base64(payload.image_base64, label="image")
        if payload.image_base64
        else None
    )

    result = create_patient_intelligently(
        source=payload.source,
        text=payload.text,
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        audio_bytes=audio_bytes,
        image_bytes=image_bytes,
        image_mime_type=payload.image_mime_type,
    )
    if result is None:
        raise HTTPException(
            status_code=422,
            detail="Could not extract full_name and phone_number from input",
        )

    return _creation_to_response(result)


def capture_to_response(result: CaptureResult) -> CaptureResponse:
    return CaptureResponse(
        patient_id=result.patient_id,
        full_name=result.full_name,
        phone_number=result.phone_number,
        created=result.created,
        source=result.source,
    )

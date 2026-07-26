"""Electronic Medical Record (EMR) API."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import DASHBOARD_API_KEY, PATIENT_INTAKE_API_KEY
from app.db.connection import init_db
from app.services.emr_service import (
    build_patient_emr,
    build_patient_timeline,
    create_visit,
    edit_visit,
    get_visit_history,
)

app = FastAPI(title="Doctor Boysunov EMR API", version="1.0.0")


def _verify_api_key(api_key: str | None) -> None:
    expected = DASHBOARD_API_KEY or PATIENT_INTAKE_API_KEY
    if not expected:
        return
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


class VisitWriteRequest(BaseModel):
    visit_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    main_complaint: str | None = None
    examination_findings: str | None = None
    neurological_examination: str | None = None
    preliminary_diagnosis: str | None = None
    final_diagnosis: str | None = None
    icd10_code: str | None = None
    recommended_examinations: str | None = None
    treatment_plan: str | None = None
    procedures_performed: str | None = None
    follow_up_schedule: str | None = None
    notes: str | None = None


class VisitUpdateRequest(BaseModel):
    visit_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    main_complaint: str | None = None
    examination_findings: str | None = None
    neurological_examination: str | None = None
    preliminary_diagnosis: str | None = None
    final_diagnosis: str | None = None
    icd10_code: str | None = None
    recommended_examinations: str | None = None
    treatment_plan: str | None = None
    procedures_performed: str | None = None
    follow_up_schedule: str | None = None
    notes: str | None = None


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "emr"}


@app.get("/api/v1/emr/patient/{patient_id}")
def get_patient_emr(
    patient_id: int,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    """Full lifelong medical record for a patient."""
    _verify_api_key(x_api_key)
    try:
        return build_patient_emr(patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/emr/patient/{patient_id}/history")
def get_patient_history(
    patient_id: int,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    """Complete visit history with complaints, diagnoses, treatments, follow-ups."""
    _verify_api_key(x_api_key)
    try:
        return get_visit_history(patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/emr/patient/{patient_id}/timeline")
def get_patient_timeline(
    patient_id: int,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    """Unified chronological timeline across visits, follow-ups, and appointments."""
    _verify_api_key(x_api_key)
    try:
        return build_patient_timeline(patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/emr/patient/{patient_id}/visits")
def create_patient_visit(
    patient_id: int,
    payload: VisitWriteRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    """Create a new visit in the patient's lifelong medical record."""
    _verify_api_key(x_api_key)
    try:
        visit = create_visit(patient_id, **payload.model_dump())
        return {"success": True, "visit": visit}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/v1/emr/patient/{patient_id}/visits/{visit_id}")
def update_patient_visit(
    patient_id: int,
    visit_id: int,
    payload: VisitUpdateRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    """Edit an existing visit."""
    _verify_api_key(x_api_key)
    fields = {key: value for key, value in payload.model_dump().items() if value is not None}
    try:
        visit = edit_visit(patient_id, visit_id, **fields)
        return {"success": True, "visit": visit}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

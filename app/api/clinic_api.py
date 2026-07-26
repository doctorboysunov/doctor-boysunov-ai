"""Clinic Locator API — admin panel configuration and recommendations."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import DASHBOARD_API_KEY, PATIENT_INTAKE_API_KEY
from app.db.connection import init_db
from app.repositories.clinic_repository import (
    create_clinic_location,
    deactivate_clinic_location,
    get_clinic_location,
    list_clinic_locations,
    update_clinic_location,
)
from app.services.clinic_locator_service import recommend_clinic_for_patient

app = FastAPI(title="Doctor Boysunov Clinic Locator API", version="1.0.0")


def _verify_api_key(api_key: str | None) -> None:
    expected = DASHBOARD_API_KEY or PATIENT_INTAKE_API_KEY
    if not expected:
        return
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


class ClinicWriteRequest(BaseModel):
    clinic_name: str = Field(..., min_length=1)
    staff_name: str = Field(..., min_length=1)
    role: str = Field(..., pattern=r"^(doctor|student|assistant)$")
    address: str = Field(..., min_length=1)
    latitude: float
    longitude: float
    specialty: str | None = None
    google_maps_link: str | None = None
    working_days: str = "mon,tue,wed,thu,fri"
    working_hours_start: str = "09:00"
    working_hours_end: str = "18:00"
    phone: str | None = None
    services: str | None = None
    sort_priority: int = 100
    is_active: bool = True


class ClinicUpdateRequest(BaseModel):
    clinic_name: str | None = None
    staff_name: str | None = None
    role: str | None = Field(default=None, pattern=r"^(doctor|student|assistant)$")
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    specialty: str | None = None
    google_maps_link: str | None = None
    working_days: str | None = None
    working_hours_start: str | None = None
    working_hours_end: str | None = None
    phone: str | None = None
    services: str | None = None
    sort_priority: int | None = None
    is_active: bool | None = None


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "clinic-locator"}


@app.get("/api/v1/clinics")
def list_clinics(
    active_only: bool = True,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    clinics = list_clinic_locations(active_only=active_only)
    return {"count": len(clinics), "clinics": clinics}


@app.post("/api/v1/clinics")
def create_clinic(
    payload: ClinicWriteRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    try:
        clinic = create_clinic_location(**payload.model_dump())
        return {"success": True, "clinic": clinic}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/clinics/recommend/{patient_id}")
def recommend_clinic(
    patient_id: int,
    specialty: str | None = None,
    appointment_date: str | None = None,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    recommendation = recommend_clinic_for_patient(
        patient_id,
        specialty=specialty,
        appointment_date=appointment_date,
    )
    if recommendation is None:
        raise HTTPException(status_code=404, detail="No suitable clinic found")
    return recommendation


@app.get("/api/v1/clinics/{clinic_id}")
def get_clinic(
    clinic_id: int,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    clinic = get_clinic_location(clinic_id)
    if clinic is None:
        raise HTTPException(status_code=404, detail="Clinic not found")
    return clinic


@app.put("/api/v1/clinics/{clinic_id}")
def update_clinic(
    clinic_id: int,
    payload: ClinicUpdateRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    fields = {key: value for key, value in payload.model_dump().items() if value is not None}
    try:
        clinic = update_clinic_location(clinic_id, **fields)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if clinic is None:
        raise HTTPException(status_code=404, detail="Clinic not found")
    return {"success": True, "clinic": clinic}


@app.delete("/api/v1/clinics/{clinic_id}")
def delete_clinic(
    clinic_id: int,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    clinic = deactivate_clinic_location(clinic_id)
    if clinic is None:
        raise HTTPException(status_code=404, detail="Clinic not found")
    return {"success": True, "clinic": clinic}


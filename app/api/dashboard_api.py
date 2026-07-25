"""Doctor Dashboard API for Web and Mobile."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import DASHBOARD_API_KEY, PATIENT_INTAKE_API_KEY
from app.db.connection import init_db
from app.repositories.dashboard_repository import get_latest_dashboard_snapshot
from app.services.dashboard_actions import (
    action_book_appointment,
    action_mark_follow_up_completed,
    action_open_patient_card,
    action_reschedule_follow_up,
    action_send_sms,
    action_send_telegram,
)
from app.services.dashboard_service import build_doctor_dashboard, generate_morning_dashboard

app = FastAPI(title="Doctor Boysunov Dashboard API", version="1.0.0")

VALID_PERIODS = ("today", "tomorrow", "week", "month")


def _verify_api_key(api_key: str | None) -> None:
    expected = DASHBOARD_API_KEY or PATIENT_INTAKE_API_KEY
    if not expected:
        return
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


class MessageActionRequest(BaseModel):
    patient_id: int
    text: str = Field(..., min_length=1)


class RescheduleFollowUpRequest(BaseModel):
    follow_up_id: int
    scheduled_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")


class MarkCompletedRequest(BaseModel):
    follow_up_id: int


class BookAppointmentRequest(BaseModel):
    patient_id: int
    doctor_name: str
    appointment_date: str
    appointment_time: str
    complaint: str


class DashboardResponse(BaseModel):
    generated_at: str
    period: str
    period_label: str
    date_range: dict[str, str]
    as_of_date: str
    appointments_today: list[dict[str, Any]]
    follow_ups_today: list[dict[str, Any]]
    follow_ups_due: list[dict[str, Any]]
    follow_up_buckets: dict[str, list[dict[str, Any]]]
    high_priority_patients: list[dict[str, Any]]
    non_responders: list[dict[str, Any]]
    new_patients_today: list[dict[str, Any]]
    upcoming_appointments: list[dict[str, Any]]
    missed_appointments: list[dict[str, Any]]
    statistics: dict[str, int]
    ai_recommendations: list[str]
    filters: list[str]
    layout: dict[str, Any]


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "dashboard"}


@app.get("/api/v1/dashboard", response_model=DashboardResponse)
def get_dashboard(
    period: str = "today",
    anchor_date: str | None = None,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> DashboardResponse:
    """Live dashboard — recomputed on every request for real-time updates."""
    _verify_api_key(x_api_key)
    if period not in VALID_PERIODS:
        raise HTTPException(status_code=400, detail=f"Invalid period. Use: {VALID_PERIODS}")
    payload = build_doctor_dashboard(period=period, anchor_date=anchor_date)
    return DashboardResponse(**payload)


@app.post("/api/v1/dashboard/generate")
def generate_dashboard(
    period: str = "today",
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    if period not in VALID_PERIODS:
        raise HTTPException(status_code=400, detail=f"Invalid period. Use: {VALID_PERIODS}")
    dashboard = generate_morning_dashboard(period=period)
    return {"success": True, "snapshot_date": dashboard["as_of_date"], "period": period}


@app.get("/api/v1/dashboard/snapshot")
def get_snapshot(
    snapshot_date: str,
    period: str = "today",
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    snapshot = get_latest_dashboard_snapshot(snapshot_date=snapshot_date, period=period)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@app.get("/api/v1/dashboard/patient/{patient_id}")
async def patient_card(
    patient_id: int,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    try:
        return await action_open_patient_card(patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/dashboard/actions/send-telegram")
async def send_telegram_action(
    payload: MessageActionRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    return await action_send_telegram(
        patient_id=payload.patient_id,
        text=payload.text,
        bot=None,
    )


@app.post("/api/v1/dashboard/actions/send-sms")
async def send_sms_action(
    payload: MessageActionRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    return await action_send_sms(patient_id=payload.patient_id, text=payload.text)


@app.post("/api/v1/dashboard/actions/mark-completed")
async def mark_completed_action(
    payload: MarkCompletedRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    try:
        return await action_mark_follow_up_completed(payload.follow_up_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/dashboard/actions/reschedule-follow-up")
async def reschedule_follow_up_action(
    payload: RescheduleFollowUpRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    try:
        return await action_reschedule_follow_up(
            payload.follow_up_id,
            scheduled_date=payload.scheduled_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/dashboard/actions/book-appointment")
async def book_appointment_action(
    payload: BookAppointmentRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _verify_api_key(x_api_key)
    return await action_book_appointment(
        patient_id=payload.patient_id,
        doctor_name=payload.doctor_name,
        appointment_date=payload.appointment_date,
        appointment_time=payload.appointment_time,
        complaint=payload.complaint,
    )

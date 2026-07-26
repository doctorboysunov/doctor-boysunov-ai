"""Medical OS V1 — unified Platform API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.api.deps import verify_api_key
from app.db.connection import init_db
from app.medical_brain.contract import CONTRACT_VERSION as BRAIN_CONTRACT_VERSION
from app.repositories.consultation_repository import get_session_by_id
from app.services.dashboard_service import build_doctor_dashboard
from app.services.emr_ai_service import get_ai_assessment, list_pending_reviews, review_visit
from app.services.emr_service import build_patient_emr, build_patient_timeline, edit_visit, get_visit_history

PLATFORM_VERSION = "1.0.0"
WEB_DIR = Path(__file__).resolve().parents[1] / "web" / "dashboard"

app = FastAPI(
    title="Medical OS Platform API",
    version=PLATFORM_VERSION,
    description="Production clinical platform — Medical Brain, EMR, Doctor Dashboard",
)

router = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_api_key)])


class VisitReviewRequest(BaseModel):
    doctor_id: str = Field(..., min_length=1)
    final_diagnosis: str | None = None
    preliminary_diagnosis: str | None = None
    treatment_plan: str | None = None
    examination_findings: str | None = None
    notes: str | None = None
    approve: bool = True


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/v1/health")
def health_public() -> dict[str, str]:
    return {"status": "ok", "platform": "medical-os", "version": PLATFORM_VERSION}


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "platform": "medical-os",
        "version": PLATFORM_VERSION,
        "medical_brain_contract": BRAIN_CONTRACT_VERSION,
    }


@router.get("/platform/info")
def platform_info() -> dict[str, Any]:
    return {
        "name": "Medical OS",
        "version": PLATFORM_VERSION,
        "medical_brain_contract": BRAIN_CONTRACT_VERSION,
        "modules": ["medical_brain", "emr", "doctor_dashboard", "consultations"],
        "dashboard_url": "/dashboard/",
    }


# --- EMR ---

@router.get("/emr/reviews/pending")
def pending_ai_reviews(limit: int = 50) -> dict[str, Any]:
    """Visits with AI-generated drafts awaiting doctor review."""
    visits = list_pending_reviews(limit=limit)
    return {"count": len(visits), "visits": visits}


@router.get("/emr/patient/{patient_id}")
def get_patient_emr(patient_id: int) -> dict[str, Any]:
    try:
        return build_patient_emr(patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/emr/patient/{patient_id}/timeline")
def get_patient_timeline(patient_id: int) -> dict[str, Any]:
    try:
        return build_patient_timeline(patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/emr/patient/{patient_id}/history")
def get_patient_history(patient_id: int) -> dict[str, Any]:
    try:
        return get_visit_history(patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/emr/visits/{visit_id}/ai-assessment")
def get_visit_ai_assessment(visit_id: int) -> dict[str, Any]:
    assessment = get_ai_assessment(visit_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="No AI assessment for this visit")
    return {"visit_id": visit_id, "assessment": assessment}


@router.post("/emr/visits/{visit_id}/review")
def submit_visit_review(visit_id: int, payload: VisitReviewRequest) -> dict[str, Any]:
    try:
        visit = review_visit(
            visit_id,
            doctor_id=payload.doctor_id,
            final_diagnosis=payload.final_diagnosis,
            preliminary_diagnosis=payload.preliminary_diagnosis,
            treatment_plan=payload.treatment_plan,
            examination_findings=payload.examination_findings,
            notes=payload.notes,
            approve=payload.approve,
        )
        return {"success": True, "visit": visit}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# --- Dashboard ---

@router.get("/dashboard")
def get_dashboard(period: str = "today", anchor_date: str | None = None) -> dict[str, Any]:
    if period not in ("today", "tomorrow", "week", "month"):
        raise HTTPException(status_code=400, detail="Invalid period")
    return build_doctor_dashboard(period=period, anchor_date=anchor_date)


# --- Consultations ---

@router.get("/consultations/{session_id}")
def get_consultation(session_id: int) -> dict[str, Any]:
    session = get_session_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": session.id,
        "patient_id": session.patient_id,
        "visit_id": session.visit_id,
        "complaint_category": session.complaint_category,
        "phase": session.phase,
        "answers": session.answers,
        "summary": session.summary,
    }


app.include_router(router)

if WEB_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=str(WEB_DIR), html=True), name="dashboard")


@app.get("/", response_model=None)
def root():
    index = WEB_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Medical OS Platform API", "docs": "/docs"}

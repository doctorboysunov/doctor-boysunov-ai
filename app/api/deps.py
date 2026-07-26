"""Shared API dependencies."""

from __future__ import annotations

from fastapi import Header, HTTPException

from app.config import DASHBOARD_API_KEY, PATIENT_INTAKE_API_KEY


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected = DASHBOARD_API_KEY or PATIENT_INTAKE_API_KEY
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")

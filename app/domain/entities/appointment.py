"""Appointment entity — clinic booking request."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Appointment:
    id: int
    patient_id: int
    doctor_name: str
    appointment_date: str
    appointment_time: str
    complaint: str
    status: str = "pending"
    created_at: str = ""

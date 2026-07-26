"""Appointment repository interface."""

from __future__ import annotations

from typing import Protocol

from app.domain.entities.appointment import Appointment


class AppointmentRepository(Protocol):
    def create_appointment(
        self,
        *,
        patient_id: int,
        doctor_name: str,
        appointment_date: str,
        appointment_time: str,
        complaint: str,
        status: str = "pending",
    ) -> int: ...

    def get_patient_appointments(self, patient_id: int) -> list[Appointment]: ...

    def update_status(self, appointment_id: int, status: str) -> None: ...

    def cancel_appointment(self, appointment_id: int) -> None: ...

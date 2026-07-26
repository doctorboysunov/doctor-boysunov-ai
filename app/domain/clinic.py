"""Clinic location domain types."""

from __future__ import annotations

from typing import Literal

ClinicRole = Literal["doctor", "student", "assistant"]

CLINIC_ROLES: tuple[str, ...] = ("doctor", "student", "assistant")

ROLE_PRIORITY: dict[str, int] = {
    "doctor": 0,
    "student": 1,
    "assistant": 2,
}

DEFAULT_WORKING_DAYS = "mon,tue,wed,thu,fri"
DEFAULT_WORKING_HOURS_START = "09:00"
DEFAULT_WORKING_HOURS_END = "18:00"
APPOINTMENT_SLOT_MINUTES = 30

WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

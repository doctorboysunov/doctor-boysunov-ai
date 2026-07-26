"""AI Care Manager — patient monitoring outcomes and events."""

from __future__ import annotations

from typing import Literal

CareOutcome = Literal["pending", "good", "no_change", "worse", "no_response"]

CARE_OUTCOMES: tuple[str, ...] = (
    "pending",
    "good",
    "no_change",
    "worse",
    "no_response",
)

CareEventType = Literal[
    "check_in_sent",
    "examination_invite",
    "preventive_invite",
    "reply_received",
    "retry_sent",
    "no_response_marked",
    "doctor_notified",
]

CARE_EVENT_TYPES: tuple[str, ...] = (
    "check_in_sent",
    "examination_invite",
    "preventive_invite",
    "reply_received",
    "retry_sent",
    "no_response_marked",
    "doctor_notified",
)

CARE_MANAGER_RETRY_DAYS = 2

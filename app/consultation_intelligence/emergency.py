"""Staged emergency evaluation — no escalation on flag count alone."""

from __future__ import annotations

import re

from app.consultation_intelligence.answer_parser import is_negative, is_positive
from app.consultation_intelligence.state import ConsultationState, EmergencyStatus

_ACUTE_OPENING = (
    "hushdan ket", "hush yo'q", "103", "insult", "falaj", "nutq buzildi",
    "qo'lim ishlamay qoldi", "birdan falaj", "can't move", "cannot move",
)

_CONFIRMED_SCREEN_SLUGS = (
    "cauda", "stroke", "central", "seizure", "snoop", "myelo", "active_seizure",
)


def screen_message_flags(message: str) -> list[str]:
    """Lightweight screen — suspicion only, not emergency action."""
    lowered = (message or "").lower()
    suspects: list[str] = []
    if any(w in lowered for w in _ACUTE_OPENING):
        suspects.append("acute_neurological_presentation")
    if re.search(r"ikki\s*oyoq\s*kuchsiz|siydik\s*tutolmay|hojatxonaga\s*qiyin", lowered):
        suspects.append("cauda_equina_suspect")
    return suspects


def update_emergency_from_pending_answer(state: ConsultationState) -> None:
    """Promote suspected → confirmed only when screening answer is positive."""
    if not state.pending_topic and state.facts:
        last = state.facts[-1]
        slug = last.topic_slug
        parsed = last.parsed_value or last.raw_answer
        if any(k in slug for k in _CONFIRMED_SCREEN_SLUGS):
            if is_positive(parsed):
                state.emergency_status = EmergencyStatus.CONFIRMED
                state.confirmed_red_flags.append(f"{slug}:positive")
            elif is_negative(parsed):
                if state.emergency_status == EmergencyStatus.SUSPECTED:
                    state.emergency_status = EmergencyStatus.NONE
                    state.emergency_suspect_flags.clear()


def apply_message_screen(state: ConsultationState, message: str) -> None:
    suspects = screen_message_flags(message)
    if suspects and state.emergency_status == EmergencyStatus.NONE:
        state.emergency_suspect_flags = suspects
        state.emergency_status = EmergencyStatus.SUSPECTED


def is_confirmed_emergency(state: ConsultationState) -> bool:
    return state.emergency_status == EmergencyStatus.CONFIRMED

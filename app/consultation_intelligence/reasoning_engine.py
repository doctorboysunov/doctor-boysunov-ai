"""Backward-compatible adapter — delegates to ConsultationController (v6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.consultation_intelligence.controller import process_consultation_intelligence_turn
from app.consultation_intelligence.state import ConsultationState, ENGINE_VERSION
from app.domain.consultation import ComplaintCategory


@dataclass
class IntelligenceTurnOutput:
    patient_reply: str = ""
    ready_for_help_menu: bool = False
    brief_summary_for_patient: str = ""
    known_facts: dict[str, Any] = field(default_factory=dict)
    topics_covered: list[str] = field(default_factory=list)
    doctor_emr: dict[str, Any] = field(default_factory=dict)
    session_summary: dict[str, Any] = field(default_factory=dict)
    consultation_state: ConsultationState = field(default_factory=ConsultationState)
    suggests_emergency: bool = False
    emergency_flags: list[str] = field(default_factory=list)
    engine_version: str = ENGINE_VERSION


def process_intelligence_turn(
    *,
    user_message: str,
    session_messages: list[dict[str, str]],
    known_facts: dict[str, Any],
    topics_covered: list[str] | None = None,
    complaint_category: ComplaintCategory | str = "neuropathy",
) -> IntelligenceTurnOutput:
    answers = dict(known_facts or {})
    if topics_covered is not None:
        answers["topics_covered"] = list(topics_covered)

    result = process_consultation_intelligence_turn(
        user_message=user_message,
        session_messages=session_messages,
        answers=answers,
    )
    state = result.consultation_state
    return IntelligenceTurnOutput(
        patient_reply=result.patient_reply,
        ready_for_help_menu=result.ready_for_help_menu,
        brief_summary_for_patient=result.brief_summary_for_patient,
        known_facts=answers,
        topics_covered=list(state.answered_slugs),
        doctor_emr=result.doctor_emr,
        session_summary=result.session_summary,
        consultation_state=state,
        suggests_emergency=result.suggests_emergency,
        emergency_flags=result.emergency_flags,
        engine_version=ENGINE_VERSION,
    )

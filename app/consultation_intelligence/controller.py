"""ConsultationController — single orchestrator for clinical turns."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.clinical_brain.types import DoctorEmrUpdate
from app.consultation_intelligence.advice_engine import generate_personalized_advice
from app.consultation_intelligence.answer_parser import parse_answer
from app.consultation_intelligence.clinical_reasoner import ClinicalReasoner
from app.consultation_intelligence.decision_engine import DecisionEngine
from app.consultation_intelligence.emergency import (
    apply_message_screen,
    is_confirmed_emergency,
    update_emergency_from_pending_answer,
)
from app.consultation_intelligence.message_intent import is_advice_question
from app.consultation_intelligence.new_symptom_engine import (
    is_additive_symptom_message,
    merge_new_symptoms,
)
from app.consultation_intelligence.response_generator import ResponseGenerator
from app.consultation_intelligence.state import ConsultationStage, ConsultationState, ENGINE_VERSION

logger = logging.getLogger("doctor_boysunov.consultation_controller")


@dataclass
class ControllerTurnResult:
    patient_reply: str = ""
    ready_for_help_menu: bool = False
    brief_summary_for_patient: str = ""
    suggests_emergency: bool = False
    emergency_flags: list[str] = field(default_factory=list)
    doctor_emr: dict[str, Any] = field(default_factory=dict)
    session_summary: dict[str, Any] = field(default_factory=dict)
    consultation_state: ConsultationState = field(default_factory=ConsultationState)
    engine_version: str = ENGINE_VERSION


def _narrative(messages: list[dict[str, str]], user_message: str) -> str:
    parts = [m["content"] for m in messages if m.get("role") == "user" and m.get("content")]
    if not parts or parts[-1] != user_message:
        parts.append(user_message)
    return " ".join(parts)


def _is_greeting_only(text: str) -> bool:
    lowered = text.strip().lower()
    if lowered in {"salom", "assalomu alaykum", "assalom", "hello", "hi", "hayrli kun"}:
        return True
    return len(lowered.split()) <= 3 and any(w in lowered for w in ("salom", "assalom", "hello"))


def _wants_new_complaint(text: str) -> bool:
    lowered = text.strip().lower()
    return any(p in lowered for p in ("yangi muammo", "boshqa shikoyat", "restart", "boshqadan"))


def _pending_question_text(state: ConsultationState) -> str:
    if not state.pending_topic:
        return ""
    for asked in reversed(state.asked):
        if asked.topic_slug == state.pending_topic:
            return asked.question_text
    return ""


class ConsultationController:
    """Single controller: state → reason → decide → respond."""

    def __init__(self) -> None:
        self._reasoner = ClinicalReasoner()
        self._decision = DecisionEngine()
        self._responses = ResponseGenerator()

    def process_turn(
        self,
        *,
        user_message: str,
        session_messages: list[dict[str, str]],
        answers: dict[str, Any],
    ) -> ControllerTurnResult:
        state = ConsultationState.load(answers)
        result = ControllerTurnResult(consultation_state=state)

        if _is_greeting_only(user_message) and state.pathway_locked:
            pending_q = _pending_question_text(state)
            result.patient_reply = self._responses.greeting_resume(pending_q or None)
            state.persist_into(answers)
            result.consultation_state = state
            return result

        if _wants_new_complaint(user_message):
            result.patient_reply = self._responses.topic_clarification()
            state.persist_into(answers)
            result.consultation_state = state
            return result

        if is_advice_question(user_message) and state.pathway_locked:
            advice = generate_personalized_advice(state)
            pending_q = _pending_question_text(state)
            if pending_q:
                advice = f"{advice}\n\n{pending_q.rstrip('?')}?"
            result.patient_reply = advice
            state.persist_into(answers)
            result.consultation_state = state
            return result

        narrative = _narrative(session_messages, user_message)
        apply_message_screen(state, user_message)

        if not state.opening_complaint:
            state.opening_complaint = user_message
            state.record_answer("opening_complaint", user_message, user_message)

        new_symptom_ack: str | None = None
        skip_pending_answer = False
        if state.pathway_locked:
            new_symptom_ack = merge_new_symptoms(user_message, state)
            if new_symptom_ack and is_additive_symptom_message(user_message):
                skip_pending_answer = True

        if state.pending_topic and not skip_pending_answer:
            parsed = parse_answer(state.pending_topic, user_message)
            state.record_answer(state.pending_topic, user_message, parsed)
            update_emergency_from_pending_answer(state)

        state.turn_count += 1

        if not state.pathway_locked:
            self._reasoner.recognize(narrative, state)
            state.stage = ConsultationStage.COLLECTING

        self._reasoner.update(state)

        if is_confirmed_emergency(state):
            result.suggests_emergency = True
            result.emergency_flags = list(state.confirmed_red_flags)
            state.stage = ConsultationStage.EMERGENCY
            result.patient_reply = self._responses.emergency(result.emergency_flags)
            state.persist_into(answers)
            result.consultation_state = state
            return result

        decision = self._decision.decide(state)

        if decision.action == "emergency":
            result.suggests_emergency = True
            result.emergency_flags = list(state.confirmed_red_flags)
            state.stage = ConsultationStage.EMERGENCY
            result.patient_reply = self._responses.emergency(result.emergency_flags)
            state.persist_into(answers)
            result.consultation_state = state
            return result

        if decision.action == "closure":
            if state.help_menu_shown:
                result.patient_reply = self._responses.continue_after_help_action(state)
                state.stage = ConsultationStage.COLLECTING
            else:
                state.stage = ConsultationStage.CLOSURE
                result.patient_reply = self._responses.closure(state)
                result.ready_for_help_menu = True
                result.brief_summary_for_patient = (
                    f"{state.syndrome_label_uz}: {state.dominant_complaint}"[:300]
                )
                result.session_summary = self._responses.to_closure_summary(state)
                state.help_menu_shown = True
                state.stage = ConsultationStage.AWAITING_HELP
        else:
            state.record_question(decision.topic_slug, decision.question_text)
            if new_symptom_ack:
                q = decision.question_text.rstrip("?")
                result.patient_reply = (
                    f"{new_symptom_ack} ham qayd etildi. "
                    f"Bu belgi bo'yicha muhim savol: {q}?"
                )
            elif state.turn_count == 1 or len(state.answered_slugs) <= 1:
                result.patient_reply = self._responses.first_question(state, decision)
            else:
                result.patient_reply = self._responses.follow_up_question(state, decision, user_message)

        result.doctor_emr = self._emr(state)
        state.persist_into(answers)
        result.consultation_state = state
        return result

    def _emr(self, state: ConsultationState) -> dict[str, Any]:
        from app.consultation_intelligence.patient_labels import format_fact_for_patient

        doctor = DoctorEmrUpdate(
            chief_complaint=state.dominant_complaint or state.opening_complaint,
            history="; ".join(
                format_fact_for_patient(state, f) for f in state.facts[:8] if f.topic_slug != "opening_complaint"
            ),
            clinical_notes=state.recognition_rationale,
            differential_diagnoses=[d["name"] for d in state.differential[:6]],
            urgency="urgent" if state.confirmed_red_flags else "routine",
            red_flags_noted=list(state.confirmed_red_flags),
        )
        return doctor.to_dict()


_default_controller = ConsultationController()


def process_consultation_intelligence_turn(
    *,
    user_message: str,
    session_messages: list[dict[str, str]],
    answers: dict[str, Any],
) -> ControllerTurnResult:
    return _default_controller.process_turn(
        user_message=user_message,
        session_messages=session_messages,
        answers=answers,
    )

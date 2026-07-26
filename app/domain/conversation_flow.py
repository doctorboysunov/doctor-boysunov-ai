"""Conversation flow routing with explicit priority rules and trace logging."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.domain.conversation_mode import resolve_conversation_mode_with_reason
from app.domain.admin_conversation_state import registration_mode_active
from app.services.patient_intake.clinical_form import is_clinical_form_text
from app.services.patient_intake.extraction import extract_patient_from_text
from app.services.routing_trace import RoutingTrace

logger = logging.getLogger("doctor_boysunov.conversation_flow")

FlowName = Literal[
    "patient_creation",
    "patient_consultation",
    "patient_registration",
]


@dataclass(frozen=True)
class FlowDecision:
    flow: FlowName
    reason: str
    is_admin: bool
    admin_reason: str
    patient_intake_detected: bool
    patient_creation_triggered: bool
    clinical_form_detected: bool


def resolve_incoming_message_flow(
    telegram_id: int,
    text: str | None,
    *,
    trace: RoutingTrace | None = None,
) -> FlowDecision:
    """Route message flow. Admin normal text always continues to Medical AI."""
    mode, is_admin, admin_reason = resolve_conversation_mode_with_reason(telegram_id)
    normalized = (text or "").strip()

    if trace is not None:
        trace.consider("conversation_flow.resolve_incoming_message_flow")
        trace.check(
            location="conversation_flow.py",
            condition="is_admin",
            result=is_admin,
            detail=f"mode={mode} admin_reason={admin_reason}",
        )

    clinical_form = bool(normalized and is_clinical_form_text(normalized))
    extracted = extract_patient_from_text(normalized) if normalized else None
    patient_intake_detected = extracted is not None or clinical_form

    if trace is not None:
        trace.check(
            location="conversation_flow.py",
            condition="patient_intake_detected (name+phone or clinical form)",
            result=patient_intake_detected,
            detail=f"clinical_form={clinical_form} extracted={extracted is not None}",
        )

    priority1 = is_admin and (
        clinical_form
        or (patient_intake_detected and registration_mode_active(telegram_id))
    )
    if trace is not None:
        trace.check(
            location="conversation_flow.py",
            condition="priority_1: is_admin AND patient_intake_detected",
            result=priority1,
            detail="routes to patient_creation when True",
        )

    if priority1:
        decision = FlowDecision(
            flow="patient_creation",
            reason="priority_1_admin_name_phone_or_clinical_form",
            is_admin=True,
            admin_reason=admin_reason,
            patient_intake_detected=True,
            patient_creation_triggered=True,
            clinical_form_detected=clinical_form,
        )
        if trace is not None:
            trace.select("patient_creation_handler", decision.reason)
        _log_decision(telegram_id, normalized, decision)
        return decision

    if trace is not None:
        trace.check(
            location="conversation_flow.py",
            condition="priority_2: is_admin (normal conversation)",
            result=is_admin,
            detail="admin_idle REMOVED — admin normal text falls through to Medical AI",
        )

    if is_admin:
        decision = FlowDecision(
            flow="patient_consultation",
            reason="admin_normal_message_medical_ai",
            is_admin=True,
            admin_reason=admin_reason,
            patient_intake_detected=False,
            patient_creation_triggered=False,
            clinical_form_detected=False,
        )
        if trace is not None:
            trace.select("Medical AI (ask_ai)", decision.reason)
        _log_decision(telegram_id, normalized, decision)
        return decision

    if trace is not None:
        trace.check(
            location="conversation_flow.py",
            condition="priority_3: patient (non-admin)",
            result=True,
            detail="patient self-registration path",
        )

    decision = FlowDecision(
        flow="patient_registration",
        reason="priority_3_patient_self_registration",
        is_admin=False,
        admin_reason=admin_reason,
        patient_intake_detected=patient_intake_detected,
        patient_creation_triggered=False,
        clinical_form_detected=False,
    )
    if trace is not None:
        trace.select("patient_registration / location / AI chain", decision.reason)
    _log_decision(telegram_id, normalized, decision)
    return decision


def mark_consultation_flow(decision: FlowDecision) -> FlowDecision:
    """Patient finished registration — continue to AI consultation."""
    return FlowDecision(
        flow="patient_consultation",
        reason="patient_location_complete_consultation",
        is_admin=decision.is_admin,
        admin_reason=decision.admin_reason,
        patient_intake_detected=decision.patient_intake_detected,
        patient_creation_triggered=False,
        clinical_form_detected=decision.clinical_form_detected,
    )


def _log_decision(telegram_id: int, text: str, decision: FlowDecision) -> None:
    msg = (
        f"conversation_flow telegram_user_id={telegram_id} "
        f"selected_flow={decision.flow} reason={decision.reason} "
        f"is_admin={decision.is_admin} patient_intake_detected={decision.patient_intake_detected} "
        f"patient_creation_triggered={decision.patient_creation_triggered} text={text[:120]!r}"
    )
    logger.info(msg)
    print(f"=== CONVERSATION ROUTING ===\n{msg}")

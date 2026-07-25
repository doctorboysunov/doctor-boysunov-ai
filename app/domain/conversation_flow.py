"""Conversation flow routing with explicit priority rules."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.domain.conversation_mode import resolve_conversation_mode_with_reason
from app.services.patient_intake.clinical_form import is_clinical_form_text
from app.services.patient_intake.extraction import extract_patient_from_text

logger = logging.getLogger("doctor_boysunov.conversation_flow")

FlowName = Literal[
    "patient_creation",
    "admin_idle",
    "patient_registration",
    "patient_consultation",
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
) -> FlowDecision:
    """Apply routing priority: name+phone intake, admin guard, then patient registration."""
    mode, is_admin, admin_reason = resolve_conversation_mode_with_reason(telegram_id)
    normalized = (text or "").strip()

    clinical_form = bool(normalized and is_clinical_form_text(normalized))
    extracted = extract_patient_from_text(normalized) if normalized else None
    patient_intake_detected = extracted is not None or clinical_form

    # Priority 1 — name + phone (or clinical form) → patient creation for admin.
    if is_admin and patient_intake_detected:
        decision = FlowDecision(
            flow="patient_creation",
            reason="priority_1_admin_name_phone_or_clinical_form",
            is_admin=True,
            admin_reason=admin_reason,
            patient_intake_detected=True,
            patient_creation_triggered=True,
            clinical_form_detected=clinical_form,
        )
        _log_decision(telegram_id, normalized, decision)
        return decision

    # Priority 2 — admin never enters registration / receptionist onboarding.
    if is_admin:
        decision = FlowDecision(
            flow="admin_idle",
            reason="priority_2_admin_mode_skip_registration",
            is_admin=True,
            admin_reason=admin_reason,
            patient_intake_detected=False,
            patient_creation_triggered=False,
            clinical_form_detected=False,
        )
        _log_decision(telegram_id, normalized, decision)
        return decision

    # Priority 3 — patient self-registration and consultation.
    decision = FlowDecision(
        flow="patient_registration",
        reason="priority_3_patient_self_registration",
        is_admin=False,
        admin_reason=admin_reason,
        patient_intake_detected=patient_intake_detected,
        patient_creation_triggered=False,
        clinical_form_detected=False,
    )
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

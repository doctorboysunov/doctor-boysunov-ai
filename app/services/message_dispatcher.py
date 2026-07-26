"""Map classified intents to handler modules."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.intent_types import MessageIntent, TargetModule
from app.services.intent_router import IntentClassification


@dataclass(frozen=True)
class RouteDecision:
    module: TargetModule
    intent: MessageIntent
    reason: str
    classification: IntentClassification


def resolve_target_module(
    classification: IntentClassification,
    *,
    is_admin: bool,
    admin_active_patient_id: int | None,
    in_appointment_booking: bool = False,
    in_patient_registration_mode: bool = False,
) -> RouteDecision:
    intent = classification.intent

    if in_appointment_booking:
        return RouteDecision(
            module="appointment_booking",
            intent=intent,
            reason="appointment_booking_state_active",
            classification=classification,
        )

    if in_patient_registration_mode and intent == "new_patient":
        return RouteDecision(
            module="patient_creation",
            intent=intent,
            reason="explicit_registration_mode_patient_creation",
            classification=classification,
        )

    if intent == "follow_up":
        return RouteDecision(
            module="follow_up_reply",
            intent=intent,
            reason="pending_follow_up_reply",
            classification=classification,
        )

    if intent == "appointment":
        return RouteDecision(
            module="appointment_booking",
            intent=intent,
            reason="appointment_intent",
            classification=classification,
        )

    if intent == "clinic_location":
        return RouteDecision(
            module="clinic_locator",
            intent=intent,
            reason="clinic_location_intent",
            classification=classification,
        )

    if intent == "pricing":
        return RouteDecision(
            module="pricing_info",
            intent=intent,
            reason="pricing_intent",
            classification=classification,
        )

    if is_admin and intent == "existing_patient" and admin_active_patient_id is not None:
        return RouteDecision(
            module="doctor_visit",
            intent=intent,
            reason="admin_labeled_emr_documentation",
            classification=classification,
        )

    if intent == "medical_question":
        return RouteDecision(
            module="medical_consultation",
            intent=intent,
            reason="medical_ai_consultation",
            classification=classification,
        )

    if intent == "general_conversation":
        return RouteDecision(
            module="general_chat",
            intent=intent,
            reason="general_ai_conversation",
            classification=classification,
        )

    return RouteDecision(
        module="general_chat",
        intent=intent,
        reason="default_normal_ai_assistant",
        classification=classification,
    )

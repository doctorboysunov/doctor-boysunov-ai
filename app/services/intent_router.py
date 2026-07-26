"""AI Intent Router — classify every incoming message before module dispatch."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from openai import OpenAI

from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.domain.intent_types import MessageIntent
from app.handlers.appointments import is_booking_trigger
from app.services.doctor_visit_parser import has_labeled_clinical_fields
from app.services.patient_intake.clinical_form import is_clinical_form_text
from app.services.patient_intake.extraction import extract_patient_from_text

logger = logging.getLogger("doctor_boysunov.intent_router")

_client = OpenAI(api_key=OPENAI_API_KEY)

_MEDICAL_HINTS = (
    "og'ri",
    "ogri",
    "og‘ri",
    "og'riyapti",
    "ogriyapti",
    "hurts",
    "hurt",
    "pain",
    "ache",
    "shikoyat",
    "symptom",
    "bosh",
    "bel",
    "head",
    "qorin",
    "ko'krak",
    "ko‘krak",
    "tashxis",
    "diagnoz",
    "diagnosis",
    "davolash",
    "treatment",
    "dori",
    "tabletka",
    "tekshiruv",
    "examination",
    "mrt",
    "emg",
    "yomon",
    "worse",
    "better",
    "yaxshi",
    "nima qilay",
    "nima qilish",
    "what should i do",
    "uvish",
    "uvishmoqda",
    "numb",
    "tingling",
    "qo'l",
    "qol",
    "belim",
    "bel ",
)

_CLINIC_HINTS = (
    "klinika",
    "clinic",
    "manzil",
    "address",
    "qayerda",
    "ishlaysiz",
    "ishlaydi",
    "where",
    "location",
    "lokatsiya",
    "maps",
    "google",
    "yo'l",
    "yol",
    "filial",
)

_PRICING_HINTS = (
    "narx",
    "price",
    "pricing",
    "qancha",
    "cost",
    "to'lov",
    "tolov",
    "pul",
    "fee",
    "consultation fee",
)

_GREETING_HINTS = (
    "salom",
    "hello",
    "hi",
    "assalomu",
    "rahmat",
    "thanks",
    "thank you",
)

_VALID_AI_INTENTS = frozenset(
    {
        "new_patient",
        "existing_patient",
        "medical_question",
        "follow_up",
        "appointment",
        "clinic_location",
        "pricing",
        "general_conversation",
        "admin_command",
    }
)


@dataclass(frozen=True)
class IntentClassification:
    intent: MessageIntent
    reason: str
    method: str
    confidence: float
    has_name_phone: bool


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in hints)


def is_medical_complaint(text: str | None) -> bool:
    """True when message looks like a symptom / medical question during registration."""
    normalized = (text or "").strip()
    if not normalized:
        return False
    return _contains_any(normalized, _MEDICAL_HINTS)


def _is_strict_new_patient_intake(text: str) -> bool:
    """True only when message contains both a person's name and phone number."""
    if extract_patient_from_text(text) is not None:
        return True
    return is_clinical_form_text(text)


def _classify_with_rules(
    text: str,
    *,
    is_admin: bool,
    admin_active_patient_id: int | None,
    pending_follow_up: bool,
    in_patient_registration_mode: bool,
) -> IntentClassification:
    normalized = text.strip()
    lowered = normalized.lower()

    if lowered.startswith("/"):
        return IntentClassification(
            intent="admin_command",
            reason="message_starts_with_slash",
            method="rules",
            confidence=1.0,
            has_name_phone=False,
        )

    has_name_phone = _is_strict_new_patient_intake(normalized)
    if in_patient_registration_mode and has_name_phone:
        return IntentClassification(
            intent="new_patient",
            reason="explicit_registration_mode_name_phone",
            method="rules",
            confidence=1.0,
            has_name_phone=True,
        )

    if pending_follow_up:
        return IntentClassification(
            intent="follow_up",
            reason="pending_follow_up_reply",
            method="rules",
            confidence=0.95,
            has_name_phone=False,
        )

    if is_booking_trigger(normalized):
        return IntentClassification(
            intent="appointment",
            reason="appointment_trigger_phrase",
            method="rules",
            confidence=0.98,
            has_name_phone=False,
        )

    if _contains_any(normalized, _CLINIC_HINTS):
        return IntentClassification(
            intent="clinic_location",
            reason="clinic_location_keywords",
            method="rules",
            confidence=0.9,
            has_name_phone=False,
        )

    if _contains_any(normalized, _PRICING_HINTS):
        return IntentClassification(
            intent="pricing",
            reason="pricing_keywords",
            method="rules",
            confidence=0.9,
            has_name_phone=False,
        )

    if has_labeled_clinical_fields(normalized):
        if is_admin and admin_active_patient_id is not None:
            return IntentClassification(
                intent="existing_patient",
                reason="admin_labeled_emr_fields",
                method="rules",
                confidence=0.98,
                has_name_phone=False,
            )

    if _contains_any(normalized, _MEDICAL_HINTS):
        return IntentClassification(
            intent="medical_question",
            reason="medical_symptom_keywords",
            method="rules",
            confidence=0.88,
            has_name_phone=False,
        )

    if _contains_any(normalized, _GREETING_HINTS):
        return IntentClassification(
            intent="general_conversation",
            reason="greeting_keywords",
            method="rules",
            confidence=0.85,
            has_name_phone=False,
        )

    return IntentClassification(
        intent="general_conversation",
        reason="default_general_conversation",
        method="rules",
        confidence=0.6,
        has_name_phone=False,
    )


def _classify_with_ai(text: str) -> IntentClassification | None:
    if not OPENAI_API_KEY:
        return None

    try:
        response = _client.responses.create(
            model=OPENAI_MODEL,
            input=text,
            instructions=(
                "Classify the user message into exactly one intent:\n"
                "new_patient, existing_patient, medical_question, follow_up, appointment, "
                "clinic_location, pricing, general_conversation, admin_command.\n"
                "Use new_patient ONLY when the message clearly includes both a person's name "
                "and a phone number.\n"
                'Return strict JSON: {"intent":"...", "confidence":0.0-1.0, "reason":"..."}'
            ),
            text={"format": {"type": "json_object"}},
        )
        payload = json.loads(response.output_text)
        intent = payload.get("intent")
        if intent not in _VALID_AI_INTENTS:
            return None
        confidence = float(payload.get("confidence") or 0.75)
        reason = str(payload.get("reason") or "ai_classification")
        has_name_phone = intent == "new_patient" and extract_patient_from_text(text) is not None
        if intent == "new_patient" and not has_name_phone:
            intent = "general_conversation"
            reason = "ai_new_patient_rejected_missing_name_phone"
        return IntentClassification(
            intent=intent,
            reason=reason,
            method="ai",
            confidence=confidence,
            has_name_phone=has_name_phone,
        )
    except Exception:  # noqa: BLE001
        logger.exception("ai_intent_classification_failed text=%r", text[:120])
        return None


def classify_message_intent(
    text: str | None,
    *,
    is_admin: bool,
    admin_active_patient_id: int | None = None,
    pending_follow_up: bool = False,
    in_patient_registration_mode: bool = False,
    use_ai_fallback: bool = False,
) -> IntentClassification:
    """Classify incoming message intent. new_patient only in explicit registration mode."""
    normalized = (text or "").strip()
    if not normalized:
        return IntentClassification(
            intent="general_conversation",
            reason="empty_message",
            method="rules",
            confidence=1.0,
            has_name_phone=False,
        )

    rules = _classify_with_rules(
        normalized,
        is_admin=is_admin,
        admin_active_patient_id=admin_active_patient_id,
        pending_follow_up=pending_follow_up,
        in_patient_registration_mode=in_patient_registration_mode,
    )
    if rules.confidence >= 0.85 or rules.intent == "new_patient":
        return rules

    if use_ai_fallback:
        ai_result = _classify_with_ai(normalized)
        if ai_result is not None and ai_result.confidence >= rules.confidence:
            return ai_result

    return rules


def log_intent_classification(
    *,
    telegram_id: int,
    text: str,
    classification: IntentClassification,
    module: str,
) -> None:
    message = (
        f"intent_router incoming_message={text[:200]!r} "
        f"detected_intent={classification.intent} "
        f"selected_module={module} "
        f"method={classification.method} "
        f"confidence={classification.confidence:.2f} "
        f"reason={classification.reason} "
        f"telegram_user_id={telegram_id}"
    )
    logger.info(message)
    print(f"=== INTENT ROUTER ===\n{message}")

"""Shared incoming message routing for text and voice."""

from __future__ import annotations

import json
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.config import DATABASE_PATH
from app.domain.admin_conversation_state import (
    cancel_patient_registration,
    get_admin_state,
    registration_mode_active,
)
from app.domain.conversation_mode import is_doctor_admin_mode
from app.domain.patient_profile_fields import PROFILE_FIELDS
from app.handlers.appointments import BOOKING_STATE_KEY, handle_appointment_flow
from app.handlers.clinic_location_handler import handle_clinic_location_request
from app.handlers.common import get_telegram_user_id, register_telegram_user
from app.handlers.doctor_visit_handler import handle_doctor_visit_message
from app.handlers.location import LocationHandleResult, handle_location_registration_text
from app.handlers.patient_creation_handler import execute_patient_creation_from_text
from app.handlers.pricing_handler import handle_pricing_request
from app.repositories.communication_repository import get_pending_follow_up_reply_delivery
from app.repositories.conversation_repository import (
    get_last_messages,
    get_or_create_active_conversation,
    save_message,
)
from app.repositories.patient_profile_repository import (
    get_or_create_patient_profile,
    update_patient_profile,
)
from app.services.follow_up_reply_service import handle_follow_up_patient_reply
from app.services.intent_router import classify_message_intent, log_intent_classification
from app.services.message_dispatcher import resolve_target_module
from app.services.openai_service import ask_ai
from app.services.profile_extraction import extract_profile_updates

HISTORY_LIMIT = 10

logger = logging.getLogger("doctor_boysunov.message_router")

_AI_MODULES = frozenset({"general_chat", "medical_consultation"})
_PATIENT_DIRECT_MODULES = frozenset(
    {"follow_up_reply", "appointment_booking", "clinic_locator", "pricing_info"}
)


async def route_incoming_text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str,
    source: str = "telegram",
) -> None:
    """Classify intent, log routing decision, and dispatch to the correct module."""
    message = update.message
    if message is None:
        return

    telegram_id = get_telegram_user_id(update)
    if telegram_id is None:
        await message.reply_text("Foydalanuvchi aniqlanmadi.")
        return

    is_admin = is_doctor_admin_mode(telegram_id)
    in_patient_registration_mode = is_admin and registration_mode_active(telegram_id)
    admin_state = get_admin_state(context, admin_telegram_id=telegram_id if is_admin else None)
    admin_active_patient_id = admin_state.patient_id if admin_state else None
    in_appointment_booking = bool(
        context.user_data and context.user_data.get(BOOKING_STATE_KEY)
    )

    pending_follow_up = False
    if not is_admin:
        user_id = register_telegram_user(update)
        pending_follow_up = get_pending_follow_up_reply_delivery(user_id) is not None

    classification = classify_message_intent(
        text,
        is_admin=is_admin,
        admin_active_patient_id=admin_active_patient_id,
        pending_follow_up=pending_follow_up,
        in_patient_registration_mode=in_patient_registration_mode,
    )
    route = resolve_target_module(
        classification,
        is_admin=is_admin,
        admin_active_patient_id=admin_active_patient_id,
        in_appointment_booking=in_appointment_booking,
        in_patient_registration_mode=in_patient_registration_mode,
    )
    log_intent_classification(
        telegram_id=telegram_id,
        text=text,
        classification=classification,
        module=route.module,
    )

    if in_patient_registration_mode and route.module != "patient_creation":
        cancel_patient_registration(context, admin_telegram_id=telegram_id)
        logger.info(
            "patient_registration_auto_cancelled telegram_user_id=%s routed_module=%s",
            telegram_id,
            route.module,
        )

    if route.module == "patient_creation":
        await execute_patient_creation_from_text(
            update,
            context,
            text=text,
            source=source,
            telegram_id=telegram_id,
        )
        return

    if route.module == "doctor_visit":
        await handle_doctor_visit_message(
            update,
            context,
            text=text,
            admin_telegram_id=telegram_id,
        )
        return

    if route.module == "clinic_locator":
        user_id = register_telegram_user(update) if not is_admin else admin_active_patient_id
        await handle_clinic_location_request(update, context, patient_id=user_id)
        return

    if route.module == "pricing_info":
        await handle_pricing_request(update)
        return

    if route.module in _AI_MODULES:
        await _handle_ai_chat(
            update,
            context,
            text=text,
            conversation_mode="doctor_admin" if is_admin else "patient",
        )
        return

    user_id = register_telegram_user(update)
    conversation_id = get_or_create_active_conversation(user_id)
    save_message(conversation_id, "user", text)

    if route.module == "follow_up_reply":
        if await handle_follow_up_patient_reply(
            update,
            context,
            patient_id=user_id,
            reply_text=text,
        ):
            return

    profile_updates = extract_profile_updates(text)
    if profile_updates:
        update_patient_profile(user_id, **profile_updates)
        logger.info(
            "patient_profile_updated user_id=%s fields=%s",
            user_id,
            sorted(profile_updates),
        )

    patient_profile = get_or_create_patient_profile(user_id)

    if route.module == "appointment_booking":
        if await handle_appointment_flow(
            update,
            context,
            user_id=user_id,
            conversation_id=conversation_id,
        ):
            return

    if await handle_appointment_flow(
        update,
        context,
        user_id=user_id,
        conversation_id=conversation_id,
    ):
        return

    if route.module not in _PATIENT_DIRECT_MODULES and route.module not in _AI_MODULES:
        location_result = await handle_location_registration_text(
            update,
            context,
            user_id=user_id,
            conversation_id=conversation_id,
            patient_profile=patient_profile,
        )
        if location_result in (
            LocationHandleResult.HANDLED,
            LocationHandleResult.COMPLETED,
        ):
            return

    await _handle_ai_chat(
        update,
        context,
        text=text,
        conversation_mode="patient",
        user_id=user_id,
        conversation_id=conversation_id,
        patient_profile=patient_profile,
    )


async def _handle_ai_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str,
    conversation_mode: str,
    user_id: int | None = None,
    conversation_id: int | None = None,
    patient_profile: dict | None = None,
) -> None:
    message = update.message
    if message is None:
        return

    if user_id is None:
        user_id = register_telegram_user(update)
    if conversation_id is None:
        conversation_id = get_or_create_active_conversation(user_id)
        save_message(conversation_id, "user", text)
    if patient_profile is None:
        patient_profile = get_or_create_patient_profile(user_id)

    history = get_last_messages(conversation_id, limit=HISTORY_LIMIT)

    print("=== BEFORE ask_ai() ===")
    print(f"database={DATABASE_PATH}")
    print(f"conversation_id={conversation_id}")
    print(f"history_count={len(history)}")
    print(f"history={json.dumps(history, ensure_ascii=False, indent=2)}")
    print(
        "patient_profile="
        f"{json.dumps({k: patient_profile.get(k) for k in PROFILE_FIELDS}, ensure_ascii=False)}"
    )
    print(f"conversation_mode={conversation_mode}")

    answer = ask_ai(history, patient_profile=patient_profile, conversation_mode=conversation_mode)
    save_message(conversation_id, "assistant", answer)
    await message.reply_text(answer)

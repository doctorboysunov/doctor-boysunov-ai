import json
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.config import DATABASE_PATH
from app.domain.conversation_flow import mark_consultation_flow, resolve_incoming_message_flow
from app.domain.patient_profile_fields import PROFILE_FIELDS
from app.handlers.appointments import handle_appointment_flow
from app.handlers.common import get_telegram_user_id, register_telegram_user
from app.handlers.location import handle_location_registration_text
from app.handlers.patient_creation_handler import execute_patient_creation_from_text
from app.repositories.conversation_repository import (
    get_last_messages,
    get_or_create_active_conversation,
    save_message,
)
from app.repositories.patient_profile_repository import (
    get_or_create_patient_profile,
    update_patient_profile,
)
from app.services.location_profile import has_location_stored
from app.services.openai_service import ask_ai
from app.services.profile_extraction import extract_profile_updates

HISTORY_LIMIT = 10

logger = logging.getLogger("doctor_boysunov.chat")


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    telegram_id = get_telegram_user_id(update)
    if telegram_id is None:
        await update.message.reply_text("Foydalanuvchi aniqlanmadi.")
        return

    decision = resolve_incoming_message_flow(telegram_id, user_message)
    logger.info(
        "chat_route telegram_user_id=%s flow=%s is_admin=%s text=%r",
        telegram_id,
        decision.flow,
        decision.is_admin,
        user_message[:120],
    )

    if decision.flow == "patient_creation":
        await execute_patient_creation_from_text(
            update,
            context,
            text=user_message,
            source="telegram",
            telegram_id=telegram_id,
        )
        return

    user_id = register_telegram_user(update)
    conversation_id = get_or_create_active_conversation(user_id)
    save_message(conversation_id, "user", user_message)

    profile_updates = extract_profile_updates(user_message)
    if profile_updates:
        update_patient_profile(user_id, **profile_updates)
        logger.info(
            "patient_profile_updated user_id=%s fields=%s",
            user_id,
            sorted(profile_updates),
        )

    patient_profile = get_or_create_patient_profile(user_id)

    if not decision.is_admin:
        if await handle_location_registration_text(
            update,
            context,
            user_id=user_id,
            conversation_id=conversation_id,
            patient_profile=patient_profile,
        ):
            return

        if await handle_appointment_flow(
            update,
            context,
            user_id=user_id,
            conversation_id=conversation_id,
        ):
            return

        if not has_location_stored(patient_profile):
            return
    elif await handle_appointment_flow(
        update,
        context,
        user_id=user_id,
        conversation_id=conversation_id,
    ):
        return

    consultation = mark_consultation_flow(decision)
    conversation_mode = "doctor_admin" if decision.is_admin else "patient"
    logger.info(
        "chat_medical_ai telegram_user_id=%s conversation_mode=%s flow=%s reason=%s",
        telegram_id,
        conversation_mode,
        consultation.flow,
        consultation.reason,
    )

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

    answer = ask_ai(
        history,
        patient_profile=patient_profile,
        conversation_mode=conversation_mode,
    )

    save_message(conversation_id, "assistant", answer)
    await update.message.reply_text(answer)

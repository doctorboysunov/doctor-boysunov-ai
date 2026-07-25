import json
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.config import DATABASE_PATH
from app.domain.patient_profile_fields import PROFILE_FIELDS
from app.handlers.common import register_telegram_user
from app.repositories.conversation_repository import (
    get_last_messages,
    get_or_create_active_conversation,
    save_message,
)
from app.repositories.patient_profile_repository import (
    get_or_create_patient_profile,
    update_patient_profile,
)
from app.services.openai_service import ask_ai
from app.services.profile_extraction import extract_profile_updates

HISTORY_LIMIT = 10
logger = logging.getLogger("doctor_boysunov.chat")


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    telegram_id = update.effective_user.id

    user_id = register_telegram_user(update)

    profile_updates = extract_profile_updates(user_message)
    if profile_updates:
        update_patient_profile(user_id, **profile_updates)
        logger.info(
            "patient_profile_updated user_id=%s fields=%s",
            user_id,
            sorted(profile_updates),
        )

    patient_profile = get_or_create_patient_profile(user_id)
    conversation_id = get_or_create_active_conversation(user_id)

    save_message(conversation_id, "user", user_message)

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

    answer = ask_ai(history, patient_profile=patient_profile)

    save_message(conversation_id, "assistant", answer)
    await update.message.reply_text(answer)

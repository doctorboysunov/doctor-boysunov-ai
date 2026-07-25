"""Doctor/admin conversation mode — instant patient creation, no receptionist."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.handlers.common import get_telegram_user_id
from app.handlers.patient_creation_handler import (
    execute_patient_creation_from_text,
    send_admin_idle_hint,
)
from app.services.patient_intake.extraction import extract_patient_from_text


async def handle_admin_chat_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle admin text: create patients from name+phone, never run receptionist AI."""
    message = update.message
    if message is None or not message.text:
        return False

    telegram_id = get_telegram_user_id(update)
    if telegram_id is None:
        return False

    text = message.text
    if extract_patient_from_text(text) is None:
        await send_admin_idle_hint(update)
        return True

    return await execute_patient_creation_from_text(
        update,
        text=text,
        source="telegram",
        telegram_id=telegram_id,
    )

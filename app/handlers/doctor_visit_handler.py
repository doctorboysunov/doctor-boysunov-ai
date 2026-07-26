"""Doctor visit mode — admin documents the active patient in EMR."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.domain.admin_conversation_state import get_admin_state, update_active_visit
from app.services.doctor_visit_service import (
    format_doctor_visit_confirmation,
    record_doctor_visit_note,
)

logger = logging.getLogger("doctor_boysunov.doctor_visit_handler")


async def handle_doctor_visit_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str,
    admin_telegram_id: int | None = None,
) -> bool:
    telegram_id = admin_telegram_id
    if telegram_id is None:
        from app.handlers.common import get_telegram_user_id

        telegram_id = get_telegram_user_id(update)

    state = get_admin_state(context, admin_telegram_id=telegram_id)
    if state is None or state.patient_id is None or state.patient_name is None:
        return False

    message = update.message
    if message is None:
        return False

    try:
        result = record_doctor_visit_note(
            state.patient_id,
            text,
            visit_id=state.visit_id,
        )
    except ValueError:
        await message.reply_text(
            "Ma'lumotni saqlab bo'lmadi. Shikoyat, tashxis, tekshiruv, davolash yoki izoh yozing."
        )
        return True

    if state.visit_id != result.visit_id and telegram_id is not None:
        update_active_visit(
            context,
            admin_telegram_id=telegram_id,
            visit_id=result.visit_id,
        )

    await message.reply_text(
        format_doctor_visit_confirmation(
            patient_name=state.patient_name,
            result=result,
        )
    )
    logger.info(
        "doctor_visit_message_handled patient_id=%s visit_id=%s fields=%s",
        state.patient_id,
        result.visit_id,
        result.saved_fields,
    )
    return True

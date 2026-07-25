"""Doctor/admin conversation mode — instant patient creation, no receptionist."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.services.patient_creation_engine import (
    PatientCreationResult,
    create_patient_intelligently,
    format_admin_creation_confirmation,
)
from app.services.patient_intake.clinical_form import is_clinical_form_text
from app.services.patient_intake.extraction import extract_patient_from_text
from app.services.patient_intake.service import capture_clinical_form

logger = logging.getLogger("doctor_boysunov.admin_conversation")

ADMIN_HINT = (
    "Bemor qo'shish uchun ism va telefon yuboring.\n"
    "Masalan: Ali Valiyev 901234567"
)


async def handle_admin_chat_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle admin text: create patients from name+phone, never run receptionist AI."""
    message = update.message
    if message is None or not message.text:
        return False

    text = message.text

    if is_clinical_form_text(text):
        result = capture_clinical_form(text, source="telegram", telegram_id=None)
        if result is None:
            return False

        await message.reply_text(
            format_admin_creation_confirmation(
                PatientCreationResult(
                    patient_id=result.patient_id,
                    full_name=result.full_name,
                    phone_number=result.phone_number,
                    created=result.created,
                    source=result.source,
                    treatment_id=None,
                    treatment_started=False,
                    medical_record_id=None,
                    follow_up_count=0,
                    follow_up_dates=(),
                    duplicate_prevented=not result.created,
                )
            )
        )
        return True

    if extract_patient_from_text(text) is None:
        await message.reply_text(ADMIN_HINT)
        return True

    result = create_patient_intelligently(
        source="telegram",
        text=text,
        telegram_id=None,
        username=None,
    )
    if result is None:
        await message.reply_text("Ism yoki telefonni o'qib bo'lmadi.")
        return True

    await message.reply_text(format_admin_creation_confirmation(result))
    logger.info(
        "admin_patient_created patient_id=%s created=%s by_admin=%s",
        result.patient_id,
        result.created,
        update.effective_user.id,
    )
    return True

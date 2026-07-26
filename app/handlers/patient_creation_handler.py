"""Shared patient creation from text (Telegram text or voice transcript)."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.domain.admin_conversation_state import enter_normal_ai_mode
from app.domain.conversation_mode import is_doctor_admin_mode
from app.services.patient_creation_engine import (
    PatientCreationResult,
    create_patient_intelligently,
    format_admin_creation_confirmation,
)
from app.services.patient_intake.clinical_form import is_clinical_form_text
from app.services.patient_intake.service import capture_clinical_form

logger = logging.getLogger("doctor_boysunov.patient_creation_handler")

NORMAL_AI_HINT = (
    "Normal AI assistant mode active.\n"
    "Savollaringizni yozing: tibbiy maslahat, klinika, navbat, narx, joylashuv."
)


def _complete_admin_patient_creation(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    admin_telegram_id: int,
    patient_id: int | None = None,
    patient_name: str | None = None,
) -> None:
    if is_doctor_admin_mode(admin_telegram_id):
        enter_normal_ai_mode(
            context,
            admin_telegram_id=admin_telegram_id,
            patient_id=patient_id,
            patient_name=patient_name,
        )


async def execute_patient_creation_from_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str,
    source: str,
    telegram_id: int,
) -> bool:
    """Create or find a patient from explicit name+phone intake."""
    message = update.message
    if message is None:
        return False

    if is_clinical_form_text(text):
        result = capture_clinical_form(text, source=source, telegram_id=None)
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
            + "\n\n"
            + NORMAL_AI_HINT
        )
        _complete_admin_patient_creation(
            context,
            admin_telegram_id=telegram_id,
            patient_id=result.patient_id,
            patient_name=result.full_name,
        )
        logger.info(
            "patient_creation_completed source=%s patient_id=%s by_admin=%s",
            source,
            result.patient_id,
            telegram_id,
        )
        return True

    result = create_patient_intelligently(
        source=source,
        text=text,
        telegram_id=None,
        username=None,
    )
    if result is None:
        await message.reply_text(
            "Ism yoki telefonni o'qib bo'lmadi.\n"
            "Masalan: Ali Valiyev +998701041101"
        )
        return True

    await message.reply_text(format_admin_creation_confirmation(result) + "\n\n" + NORMAL_AI_HINT)
    _complete_admin_patient_creation(
        context,
        admin_telegram_id=telegram_id,
        patient_id=result.patient_id,
        patient_name=result.full_name,
    )
    logger.info(
        "patient_creation_completed source=%s patient_id=%s created=%s by_admin=%s",
        source,
        result.patient_id,
        result.created,
        telegram_id,
    )
    return True

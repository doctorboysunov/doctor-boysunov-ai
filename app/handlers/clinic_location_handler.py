"""Clinic location requests from patients."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.services.clinic_locator_service import (
    format_clinic_recommendation_message,
    recommend_clinic_for_patient,
)

logger = logging.getLogger("doctor_boysunov.clinic_location")


async def handle_clinic_location_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    patient_id: int | None,
) -> None:
    message = update.message
    if message is None:
        return

    if patient_id is None:
        await message.reply_text(
            "Klinika manzili va yo'nalishni olish uchun avval ro'yxatdan o'ting "
            "va qabulga yoziling."
        )
        return

    recommendation = recommend_clinic_for_patient(patient_id)
    if recommendation is None:
        await message.reply_text(
            "Hozircha faol klinika manzili topilmadi. Iltimos, qabulga yozilish uchun "
            "\"Navbat olmoqchiman\" deb yozing."
        )
        return

    await message.reply_text(format_clinic_recommendation_message(recommendation))
    logger.info("clinic_location_sent patient_id=%s", patient_id)

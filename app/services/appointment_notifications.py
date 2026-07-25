"""Patient and admin notifications for appointment lifecycle."""

from __future__ import annotations

import logging
from typing import Any

from telegram import Bot

from app.services.admin_auth import get_all_admin_telegram_ids
from app.services.appointment_formatting import format_appointment_line
from app.services.communication import send_patient_message

logger = logging.getLogger("doctor_boysunov.appointment_notifications")


async def _send_patient_notification(
    bot: Bot,
    *,
    patient_id: int,
    text: str,
    source_id: str | None = None,
) -> bool:
    result = await send_patient_message(
        patient_id=patient_id,
        text=text,
        source_type="appointment",
        source_id=source_id,
        bot=bot,
    )
    if not result.success:
        logger.warning(
            "patient_notification_failed patient_id=%s attempted=%s error=%s",
            patient_id,
            result.attempted_channels,
            result.error_message,
        )
        return False

    logger.info(
        "patient_notification_sent patient_id=%s channel=%s delivery_id=%s",
        patient_id,
        result.channel,
        result.delivery_id,
    )
    return True


async def notify_admins_new_appointment(
    bot: Bot,
    appointment: dict[str, Any],
    *,
    patient_profile: dict[str, Any] | None = None,
) -> int:
    enriched = dict(appointment)
    if patient_profile:
        enriched["patient_full_name"] = patient_profile.get("full_name")
        enriched["phone_number"] = patient_profile.get("phone_number")

    text = (
        "Yangi qabul so'rovi (admin panel):\n\n"
        f"{format_appointment_line(enriched)}\n\n"
        "Bu so'rov /pending va /appointments ro'yxatida ko'rinadi."
    )

    sent = 0
    for admin_id in get_all_admin_telegram_ids():
        await bot.send_message(chat_id=admin_id, text=text)
        sent += 1
    logger.info(
        "admin_new_appointment_notified appointment_id=%s admin_count=%s",
        appointment["id"],
        sent,
    )
    return sent


async def notify_patient_appointment_confirmed(
    bot: Bot,
    appointment: dict[str, Any],
) -> bool:
    text = (
        "Qabulingiz tasdiqlandi.\n\n"
        f"So'rov raqami: {appointment['id']}\n"
        f"Sana: {appointment['appointment_date']}\n"
        f"Vaqt: {appointment['appointment_time']}\n"
        f"Shifokor: {appointment['doctor_name']}\n"
        f"Holat: {appointment['status']}"
    )
    return await _send_patient_notification(
        bot,
        patient_id=appointment["patient_id"],
        text=text,
        source_id=str(appointment["id"]),
    )


async def notify_patient_appointment_rescheduled(
    bot: Bot,
    appointment: dict[str, Any],
    *,
    previous_date: str,
    previous_time: str,
) -> bool:
    text = (
        "Qabulingiz vaqti o'zgartirildi.\n\n"
        f"So'rov raqami: {appointment['id']}\n"
        f"Avvalgi vaqt: {previous_date} {previous_time}\n"
        f"Yangi vaqt: {appointment['appointment_date']} {appointment['appointment_time']}\n"
        f"Shifokor: {appointment['doctor_name']}"
    )
    return await _send_patient_notification(
        bot,
        patient_id=appointment["patient_id"],
        text=text,
        source_id=str(appointment["id"]),
    )


async def notify_patient_appointment_cancelled(
    bot: Bot,
    appointment: dict[str, Any],
) -> bool:
    text = (
        "Qabulingiz bekor qilindi.\n\n"
        f"So'rov raqami: {appointment['id']}\n"
        f"Sana: {appointment['appointment_date']}\n"
        f"Vaqt: {appointment['appointment_time']}\n"
        f"Shifokor: {appointment['doctor_name']}\n\n"
        "Yangi qabul uchun \"Navbat olmoqchiman\" deb yozing."
    )
    return await _send_patient_notification(
        bot,
        patient_id=appointment["patient_id"],
        text=text,
        source_id=str(appointment["id"]),
    )

"""Universal patient capture — Telegram handlers (admin-only for doctor intake)."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.domain.conversation_mode import is_doctor_admin_mode
from app.services.patient_creation_engine import (
    create_patient_intelligently,
    format_admin_creation_confirmation,
)

logger = logging.getLogger("doctor_boysunov.patient_intake_handlers")


async def handle_patient_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None or message.contact is None:
        return

    user = update.effective_user
    if not is_doctor_admin_mode(user.id):
        await message.reply_text(
            "Kontaktni faqat shifokor/administrator qabul qiladi. "
            "Iltimos, shikoyatingizni yozing."
        )
        return

    contact = message.contact
    full_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
    if not full_name:
        full_name = contact.first_name or "Unknown"

    result = create_patient_intelligently(
        source="contact",
        full_name=full_name,
        phone_number=contact.phone_number or "",
        telegram_id=None,
        username=None,
    )
    if result is None:
        await message.reply_text("Kontaktdan ism yoki telefonni o'qib bo'lmadi.")
        return

    await message.reply_text(format_admin_creation_confirmation(result))


async def handle_patient_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None or message.voice is None:
        return

    user = update.effective_user
    if not is_doctor_admin_mode(user.id):
        await message.reply_text(
            "Ovozli xabar qabul qilindi. Iltimos, shikoyatingizni matn ko'rinishida yozing."
        )
        return

    voice = message.voice
    telegram_file = await voice.get_file()
    audio_bytes = bytes(await telegram_file.download_as_bytearray())

    result = create_patient_intelligently(
        source="voice",
        audio_bytes=audio_bytes,
        telegram_id=None,
        username=None,
    )
    if result is None:
        await message.reply_text(
            "Ovozli xabardan ism va telefon raqamini aniqlab bo'lmadi."
        )
        return

    await message.reply_text(format_admin_creation_confirmation(result))


async def try_capture_from_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.message
    if message is None or not message.photo:
        return False

    user = update.effective_user
    if not is_doctor_admin_mode(user.id):
        return False

    photo = message.photo[-1]
    telegram_file = await photo.get_file()
    image_bytes = bytes(await telegram_file.download_as_bytearray())

    result = create_patient_intelligently(
        source="ocr",
        image_bytes=image_bytes,
        image_mime_type="image/jpeg",
        telegram_id=None,
        username=None,
    )
    if result is None:
        return False

    await message.reply_text(format_admin_creation_confirmation(result))
    return True

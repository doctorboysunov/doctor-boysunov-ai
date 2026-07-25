"""Universal patient capture — Telegram handlers (admin-only for doctor intake)."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.domain.conversation_mode import is_doctor_admin_mode
from app.handlers.chat import process_text_message
from app.handlers.common import get_telegram_user_id
from app.handlers.patient_creation_handler import NORMAL_AI_HINT
from app.services.patient_creation_engine import (
    create_patient_intelligently,
    format_admin_creation_confirmation,
)
from app.services.patient_intake.transcribe import transcribe_audio

logger = logging.getLogger("doctor_boysunov.patient_intake_handlers")


async def _download_telegram_file(context: ContextTypes.DEFAULT_TYPE, file_id: str) -> bytes:
    telegram_file = await context.bot.get_file(file_id)
    if not telegram_file.file_path:
        raise RuntimeError("Telegram getFile returned empty file_path")
    data = await telegram_file.download_as_bytearray()
    return bytes(data)


async def _route_transcribed_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    transcript: str,
    source: str,
) -> None:
    await process_text_message(
        update,
        context,
        transcript,
        entry_handler=f"patient_intake.py::handle_patient_voice ({source})",
    )


async def handle_patient_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None or message.contact is None:
        return

    telegram_id = get_telegram_user_id(update)
    if telegram_id is None or not is_doctor_admin_mode(telegram_id):
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

    await message.reply_text(format_admin_creation_confirmation(result) + "\n\n" + NORMAL_AI_HINT)


async def handle_patient_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None:
        logger.warning("voice_update_missing_message")
        return

    telegram_id = get_telegram_user_id(update)
    if telegram_id is None:
        logger.warning("voice_update_missing_user")
        await message.reply_text("Foydalanuvchi aniqlanmadi. Iltimos, qayta yuboring.")
        return

    voice = message.voice
    audio = message.audio
    media = voice or audio
    media_kind = "voice" if voice is not None else "audio" if audio is not None else None

    logger.info(
        "incoming_voice telegram_user_id=%s has_voice=%s has_audio=%s file_id=%s",
        telegram_id,
        voice is not None,
        audio is not None,
        media.file_id if media is not None else None,
    )

    if media is None:
        logger.warning("voice_update_no_media telegram_user_id=%s", telegram_id)
        await message.reply_text("Ovozli xabar topilmadi. Iltimos, qayta yuboring.")
        return

    try:
        audio_bytes = await _download_telegram_file(context, media.file_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "voice_download_failed telegram_user_id=%s kind=%s error=%s",
            telegram_id,
            media_kind,
            exc,
        )
        await message.reply_text(
            "Ovozli faylni yuklab bo'lmadi. Iltimos, qayta yuboring yoki matn ko'rinishida yozing."
        )
        return

    filename = "voice.ogg" if media_kind == "voice" else "audio.mp3"
    try:
        transcript = transcribe_audio(audio_bytes, filename=filename)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "voice_transcribe_failed telegram_user_id=%s error=%s",
            telegram_id,
            exc,
        )
        await message.reply_text(
            "Ovozni tanib bo'lmadi. Iltimos, aniqroq ayting yoki matn ko'rinishida yuboring."
        )
        return

    logger.info(
        "voice_transcript telegram_user_id=%s transcript=%r",
        telegram_id,
        transcript,
    )

    await _route_transcribed_text(
        update,
        context,
        transcript=transcript,
        source="voice",
    )


async def try_capture_from_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.message
    if message is None or not message.photo:
        return False

    telegram_id = get_telegram_user_id(update)
    if telegram_id is None or not is_doctor_admin_mode(telegram_id):
        return False

    photo = message.photo[-1]
    try:
        image_bytes = await _download_telegram_file(context, photo.file_id)
    except Exception:  # noqa: BLE001
        logger.exception("photo_download_failed telegram_user_id=%s", telegram_id)
        return False

    result = create_patient_intelligently(
        source="ocr",
        image_bytes=image_bytes,
        image_mime_type="image/jpeg",
        telegram_id=None,
        username=None,
    )
    if result is None:
        return False

    await message.reply_text(format_admin_creation_confirmation(result) + "\n\n" + NORMAL_AI_HINT)
    return True

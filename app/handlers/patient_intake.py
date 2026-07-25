"""Universal patient capture — Telegram handlers (admin-only for doctor intake)."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.domain.conversation_mode import is_doctor_admin_mode, resolve_conversation_mode_with_reason
from app.services.patient_creation_engine import (
    create_patient_intelligently,
    format_admin_creation_confirmation,
)

logger = logging.getLogger("doctor_boysunov.patient_intake_handlers")


async def _download_telegram_file(context: ContextTypes.DEFAULT_TYPE, file_id: str) -> bytes:
    telegram_file = await context.bot.get_file(file_id)
    if not telegram_file.file_path:
        raise RuntimeError("Telegram getFile returned empty file_path")
    data = await telegram_file.download_as_bytearray()
    return bytes(data)


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
    if message is None:
        logger.warning("voice_update_missing_message")
        return

    user = update.effective_user
    telegram_id = user.id if user else 0
    mode, is_admin_user, admin_reason = resolve_conversation_mode_with_reason(telegram_id)

    voice = message.voice
    audio = message.audio
    media = voice or audio
    media_kind = "voice" if voice is not None else "audio" if audio is not None else None

    logger.info(
        "incoming_voice telegram_user_id=%s is_admin=%s selected_mode=%s reason=%s "
        "has_voice=%s has_audio=%s file_id=%s",
        telegram_id,
        is_admin_user,
        mode,
        admin_reason,
        voice is not None,
        audio is not None,
        media.file_id if media is not None else None,
    )

    if media is None:
        logger.warning("voice_update_no_media telegram_user_id=%s", telegram_id)
        await message.reply_text("Ovozli xabar topilmadi. Iltimos, qayta yuboring.")
        return

    if not is_admin_user:
        await message.reply_text(
            "Ovozli xabar qabul qilindi. Iltimos, shikoyatingizni matn ko'rinishida yozing."
        )
        return

    try:
        audio_bytes = await _download_telegram_file(context, media.file_id)
        logger.info(
            "voice_download_ok telegram_user_id=%s kind=%s bytes=%s",
            telegram_id,
            media_kind,
            len(audio_bytes),
        )
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

    try:
        result = create_patient_intelligently(
            source="voice",
            audio_bytes=audio_bytes,
            telegram_id=None,
            username=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "voice_processing_failed telegram_user_id=%s error=%s",
            telegram_id,
            exc,
        )
        await message.reply_text(
            "Ovozni tanib bo'lmadi. Iltimos, aniqroq ayting yoki matn ko'rinishida yuboring:\n"
            "Ali Valiyev 701041101"
        )
        return

    if result is None:
        logger.warning("voice_patient_not_extracted telegram_user_id=%s", telegram_id)
        await message.reply_text(
            "Ovozli xabardan ism va telefon raqamini aniqlab bo'lmadi.\n"
            "Masalan: \"Ali Valiyev, telefon 701041101\""
        )
        return

    confirmation = format_admin_creation_confirmation(result)
    logger.info(
        "voice_patient_processed telegram_user_id=%s patient_id=%s created=%s",
        telegram_id,
        result.patient_id,
        result.created,
    )
    await message.reply_text(confirmation)


async def try_capture_from_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.message
    if message is None or not message.photo:
        return False

    user = update.effective_user
    if not is_doctor_admin_mode(user.id):
        return False

    photo = message.photo[-1]
    try:
        image_bytes = await _download_telegram_file(context, photo.file_id)
    except Exception:  # noqa: BLE001
        logger.exception("photo_download_failed telegram_user_id=%s", user.id)
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

    await message.reply_text(format_admin_creation_confirmation(result))
    return True

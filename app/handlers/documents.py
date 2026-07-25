import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.handlers.common import register_telegram_user
from app.services.patient_file_service import link_patient_file_to_history

logger = logging.getLogger("doctor_boysunov.documents")


async def handle_patient_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None:
        return

    user_id = register_telegram_user(update)

    if message.photo:
        photo = message.photo[-1]
        telegram_file = await photo.get_file()
        file_name = f"photo_{photo.file_unique_id}.jpg"
        mime_type = "image/jpeg"
        telegram_file_id = photo.file_id
        caption = message.caption
    elif message.document:
        document = message.document
        telegram_file = await document.get_file()
        file_name = document.file_name or f"document_{document.file_unique_id}.bin"
        mime_type = document.mime_type
        telegram_file_id = document.file_id
        caption = message.caption
    else:
        return

    file_bytes = bytes(await telegram_file.download_as_bytearray())
    result = link_patient_file_to_history(
        user_id,
        file_name=file_name,
        file_bytes=file_bytes,
        mime_type=mime_type,
        caption=caption,
        telegram_file_id=telegram_file_id,
    )

    logger.info(
        "patient_file_linked user_id=%s type=%s category=%s file=%s",
        user_id,
        result["record_type"],
        result["file_category"],
        file_name,
    )

    await message.reply_text(
        "Fayl saqlandi va tibbiy tarixga qo'shildi.\n"
        f"Turi: {result['record_type']}\n"
        f"Fayl: {file_name}"
    )

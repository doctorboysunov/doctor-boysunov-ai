"""Admin commands for communication delivery management."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.repositories.communication_repository import get_delivery_record
from app.services.admin_auth import is_admin
from app.services.communication import (
    get_patient_communication_history,
    resend_delivery,
)

logger = logging.getLogger("doctor_boysunov.admin_communications")


async def _deny_unless_admin(update: Update) -> bool:
    user = update.effective_user
    if user is None or not is_admin(user.id):
        if update.message is not None:
            await update.message.reply_text("Bu buyruq faqat administratorlar uchun.")
        return False
    return True


async def admin_comm_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return

    if not context.args:
        await update.message.reply_text("Foydalanish: /comm_history <patient_id>")
        return

    try:
        patient_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Patient ID butun son bo'lishi kerak.")
        return

    history = get_patient_communication_history(patient_id)
    if not history:
        await update.message.reply_text(f"Patient {patient_id} uchun xabarlar tarixi bo'sh.")
        return

    lines = [f"Bemor {patient_id} — xabarlar tarixi ({len(history)} ta):"]
    for item in history[-10:]:
        lines.append(
            f"#{item['id']} | {item['channel']} | {item['status']} | "
            f"{item['source_type']} | {item['created_at'][:19]}"
        )
    await update.message.reply_text("\n".join(lines))


async def admin_resend_comm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return

    if not context.args:
        await update.message.reply_text("Foydalanish: /resend_comm <delivery_id>")
        return

    try:
        delivery_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Delivery ID butun son bo'lishi kerak.")
        return

    try:
        original = get_delivery_record(delivery_id)
    except ValueError:
        await update.message.reply_text(f"Delivery topilmadi: {delivery_id}")
        return

    result = await resend_delivery(delivery_id=delivery_id, bot=context.bot)
    if result.success:
        await update.message.reply_text(
            "Xabar qayta yuborildi.\n\n"
            f"Delivery ID: {result.delivery_id}\n"
            f"Patient ID: {original['patient_id']}\n"
            f"Kanal: {result.channel}\n"
            f"Holat: {result.status}"
        )
        logger.info(
            "admin_resend_comm delivery_id=%s new_delivery_id=%s channel=%s",
            delivery_id,
            result.delivery_id,
            result.channel,
        )
        return

    await update.message.reply_text(
        "Xabarni qayta yuborib bo'lmadi.\n\n"
        f"Patient ID: {original['patient_id']}\n"
        f"Urinishlar: {', '.join(result.attempted_channels) or 'yo\'q'}\n"
        f"Sabab: {result.error_message or 'noma\'lum'}"
    )

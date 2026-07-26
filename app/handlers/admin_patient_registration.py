"""Explicit admin patient registration — only via command or button."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.domain.admin_conversation_state import cancel_patient_registration, enter_patient_registration_mode
from app.handlers.common import get_telegram_user_id
from app.services.admin_auth import is_admin

REGISTRATION_PROMPT = (
    "Patient Registration mode active.\n"
    "Send patient name and phone.\n"
    "Example: Ali Valiyev +998701041101"
)

ADD_PATIENT_CALLBACK = "admin:add_patient"


def add_patient_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("➕ Add Patient", callback_data=ADD_PATIENT_CALLBACK)]]
    )


async def _deny_unless_admin(update: Update) -> int | None:
    telegram_id = get_telegram_user_id(update)
    if telegram_id is None or not is_admin(telegram_id):
        message = update.effective_message
        if message is not None:
            await message.reply_text("Bu buyruq faqat administratorlar uchun.")
        return None
    return telegram_id


async def admin_cancel_patient_registration(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    telegram_id = await _deny_unless_admin(update)
    if telegram_id is None:
        return
    cancel_patient_registration(context, admin_telegram_id=telegram_id)
    if update.message is not None:
        await update.message.reply_text(
            "Patient Registration bekor qilindi.\n"
            "Normal AI assistant rejimiga qaytdingiz."
        )


async def admin_new_patient(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = await _deny_unless_admin(update)
    if telegram_id is None:
        return
    enter_patient_registration_mode(context, admin_telegram_id=telegram_id)
    if update.message is not None:
        await update.message.reply_text(REGISTRATION_PROMPT)


async def admin_add_patient(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await admin_new_patient(update, context)


async def admin_add_patient_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    telegram_id = query.from_user.id if query.from_user else None
    if telegram_id is None or not is_admin(telegram_id):
        await query.edit_message_text("Bu tugma faqat administratorlar uchun.")
        return
    enter_patient_registration_mode(context, admin_telegram_id=telegram_id)
    await query.message.reply_text(REGISTRATION_PROMPT)

"""Administrator dashboard commands."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.services.admin_auth import is_admin
from app.services.dashboard_service import (
    build_doctor_dashboard,
    format_dashboard_telegram,
    generate_morning_dashboard,
    send_morning_dashboard_to_admins,
)

logger = logging.getLogger("doctor_boysunov.admin_dashboard")

VALID_PERIODS = ("today", "tomorrow", "week", "month")


async def _deny_unless_admin(update: Update) -> bool:
    if is_admin(update.effective_user.id):
        return True
    if update.message:
        await update.message.reply_text("Bu buyruq faqat administratorlar uchun.")
    return False


async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return

    period = context.args[0] if context.args else "today"
    if period not in VALID_PERIODS:
        await update.message.reply_text(
            "Foydalanish: /dashboard [today|tomorrow|week|month]"
        )
        return

    dashboard = build_doctor_dashboard(period=period)
    await update.message.reply_text(format_dashboard_telegram(dashboard))


async def admin_dashboard_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return

    period = context.args[0] if context.args else "today"
    if period not in VALID_PERIODS:
        await update.message.reply_text(
            "Foydalanish: /dashboard_generate [today|tomorrow|week|month]"
        )
        return

    dashboard = generate_morning_dashboard(period=period)
    await update.message.reply_text(
        "Dashboard snapshot saqlandi.\n\n" + format_dashboard_telegram(dashboard)
    )


async def admin_dashboard_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return

    sent = await send_morning_dashboard_to_admins(context.bot)
    await update.message.reply_text(f"Ertalabki dashboard yuborildi: {sent} ta admin")

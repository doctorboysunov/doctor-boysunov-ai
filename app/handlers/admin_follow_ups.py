"""Administrator follow-up schedule commands."""

from __future__ import annotations

import logging
from datetime import date

from telegram import Update
from telegram.ext import ContextTypes

from app.repositories.follow_up_repository import list_due_follow_ups, list_follow_ups_for_patient
from app.services.admin_auth import is_admin
from app.services.appointment_dates import clinic_today_iso
from app.services.follow_up_planner import (
    start_patient_follow_up_schedule,
    stop_patient_follow_up_plan,
)
from app.services.follow_up_processor import process_due_follow_ups
from app.services.follow_up_scheduler import to_iso_date

logger = logging.getLogger("doctor_boysunov.admin_follow_ups")


async def _deny_unless_admin(update: Update) -> bool:
    if is_admin(update.effective_user.id):
        return True
    if update.message:
        await update.message.reply_text("Bu buyruq faqat administratorlar uchun.")
    return False


def _format_follow_up_lines(follow_ups: list[dict]) -> str:
    if not follow_ups:
        return "Nazorat jadvali bo'sh."
    lines = []
    for item in follow_ups:
        lines.append(
            f"#{item['sequence_number']} | {item['status']} | "
            f"{item['scheduled_date']} | {item['follow_up_kind']}"
        )
    return "\n".join(lines)


async def admin_start_treatment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Foydalanish: /start_treatment <patient_id> [YYYY-MM-DD]"
        )
        return

    patient_id = int(context.args[0])
    started_at = context.args[1] if len(context.args) > 1 else to_iso_date(date.today())

    treatment = start_patient_follow_up_schedule(
        patient_id=patient_id,
        started_at=started_at,
    )
    follow_ups = list_follow_ups_for_patient(patient_id)
    await update.message.reply_text(
        "Nazorat jadvali yaratildi.\n\n"
        f"Davolanish ID: {treatment['id']}\n"
        f"Boshlangan sana: {treatment['started_at']}\n"
        f"Nazoratlar soni: {len(follow_ups)}\n\n"
        f"{_format_follow_up_lines(follow_ups)}"
    )


async def admin_followups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: /followups <patient_id>")
        return

    patient_id = int(context.args[0])
    follow_ups = list_follow_ups_for_patient(patient_id)
    await update.message.reply_text(
        f"Bemor #{patient_id} nazorat jadvali:\n\n{_format_follow_up_lines(follow_ups)}"
    )


async def admin_followups_due(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    today = clinic_today_iso()
    due_items = list_due_follow_ups(as_of_date=today)
    if not due_items:
        await update.message.reply_text(f"Bugun ({today}) nazoratlar yo'q.")
        return

    lines = [
        f"#{item['sequence_number']} patient={item['patient_id']} "
        f"date={item['scheduled_date']} kind={item['follow_up_kind']}"
        for item in due_items
    ]
    await update.message.reply_text(
        f"Bugungi nazoratlar ({today}):\n\n" + "\n".join(lines)
    )


async def admin_run_followups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    sent = await process_due_follow_ups(context.bot)
    await update.message.reply_text(f"Yuborilgan nazorat xabarlari: {sent}")


async def admin_stop_followups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: /stop_followups <patient_id>")
        return

    patient_id = int(context.args[0])
    result = stop_patient_follow_up_plan(patient_id)
    await update.message.reply_text(
        "Avtomatik nazorat to'xtatildi.\n\n"
        f"Bemor ID: {patient_id}\n"
        f"Bekor qilingan nazoratlar: {result['cancelled_follow_ups']}\n"
        f"Davolanish to'xtatildi: {'ha' if result['treatment_stopped'] else 'yo\'q'}"
    )

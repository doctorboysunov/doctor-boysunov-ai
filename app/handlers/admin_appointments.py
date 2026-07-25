"""Administrator appointment management commands."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.repositories.appointment_repository import (
    add_admin_notes,
    cancel_appointment,
    confirm_appointment,
    get_appointment,
    list_appointments,
    list_appointments_by_status,
    list_appointments_for_date,
    reschedule_appointment,
)
from app.services.admin_auth import admin_label, is_admin
from app.services.appointment_dates import clinic_today_iso, clinic_tomorrow_iso
from app.services.appointment_formatting import format_appointment_list
from app.services.appointment_notifications import (
    notify_patient_appointment_cancelled,
    notify_patient_appointment_confirmed,
    notify_patient_appointment_rescheduled,
)

logger = logging.getLogger("doctor_boysunov.admin_appointments")


def _admin_identity(update: Update) -> str:
    user = update.effective_user
    return admin_label(user.id, user.username)


async def _deny_unless_admin(update: Update) -> bool:
    if is_admin(update.effective_user.id):
        return True
    if update.message:
        await update.message.reply_text("Bu buyruq faqat administratorlar uchun.")
    return False


async def admin_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    appointments = list_appointments_for_date(clinic_today_iso())
    await update.message.reply_text(
        format_appointment_list(appointments, title=f"Bugungi qabullar ({clinic_today_iso()})")
    )


async def admin_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    tomorrow = clinic_tomorrow_iso()
    appointments = list_appointments_for_date(tomorrow)
    await update.message.reply_text(
        format_appointment_list(appointments, title=f"Ertangi qabullar ({tomorrow})")
    )


async def admin_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    appointments = list_appointments()
    await update.message.reply_text(
        format_appointment_list(appointments, title="Barcha qabullar")
    )


async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    appointments = list_appointments_by_status("pending")
    await update.message.reply_text(
        format_appointment_list(appointments, title="Kutilayotgan qabullar")
    )


async def admin_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    appointments = list_appointments_by_status("confirmed")
    await update.message.reply_text(
        format_appointment_list(appointments, title="Tasdiqlangan qabullar")
    )


async def admin_cancelled(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    appointments = list_appointments_by_status("cancelled")
    await update.message.reply_text(
        format_appointment_list(appointments, title="Bekor qilingan qabullar", include_actions=False)
    )


async def admin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: /confirm <id>")
        return

    appointment_id = int(context.args[0])
    appointment = confirm_appointment(appointment_id, confirmed_by=_admin_identity(update))
    await notify_patient_appointment_confirmed(context.bot, appointment)
    await update.message.reply_text(
        f"Qabul #{appointment_id} tasdiqlandi va bemorga xabar yuborildi."
    )


async def admin_reschedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    if len(context.args) < 3:
        await update.message.reply_text("Foydalanish: /reschedule <id> YYYY-MM-DD HH:MM")
        return

    appointment_id = int(context.args[0])
    new_date = context.args[1]
    new_time = context.args[2]
    previous = get_appointment(appointment_id)
    if previous is None:
        await update.message.reply_text(f"Qabul topilmadi: #{appointment_id}")
        return

    appointment = reschedule_appointment(
        appointment_id,
        appointment_date=new_date,
        appointment_time=new_time,
        updated_by=_admin_identity(update),
    )
    await notify_patient_appointment_rescheduled(
        context.bot,
        appointment,
        previous_date=previous["appointment_date"],
        previous_time=previous["appointment_time"],
    )
    await update.message.reply_text(
        f"Qabul #{appointment_id} vaqti yangilandi va bemorga xabar yuborildi."
    )


async def admin_cancel_appt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: /cancel_appt <id>")
        return

    appointment_id = int(context.args[0])
    appointment = cancel_appointment(
        appointment_id,
        cancelled_by=_admin_identity(update),
    )
    await notify_patient_appointment_cancelled(context.bot, appointment)
    await update.message.reply_text(
        f"Qabul #{appointment_id} bekor qilindi va bemorga xabar yuborildi."
    )


async def admin_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Foydalanish: /note <id> your notes")
        return

    appointment_id = int(context.args[0])
    notes = " ".join(context.args[1:])
    appointment = add_admin_notes(
        appointment_id,
        notes,
        updated_by=_admin_identity(update),
    )
    await update.message.reply_text(
        f"Qabul #{appointment_id} uchun eslatma saqlandi.\n\n{appointment['admin_notes']}"
    )

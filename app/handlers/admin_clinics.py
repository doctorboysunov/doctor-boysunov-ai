"""Admin clinic location management."""

from __future__ import annotations

import json
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.repositories.clinic_repository import (
    create_clinic_location,
    deactivate_clinic_location,
    get_clinic_location,
    list_clinic_locations,
)
from app.services.admin_auth import is_admin
from app.services.clinic_locator_service import (
    format_clinic_recommendation_message,
    recommend_clinic_for_patient,
)

logger = logging.getLogger("doctor_boysunov.admin_clinics")


async def _deny_unless_admin(update: Update) -> bool:
    if is_admin(update.effective_user.id):
        return True
    if update.message:
        await update.message.reply_text("Bu buyruq faqat administratorlar uchun.")
    return False


def _format_clinic_line(clinic: dict) -> str:
    return (
        f"#{clinic['id']} {clinic['clinic_name']} | {clinic['staff_name']} ({clinic['role']})\n"
        f"  {clinic['address']}\n"
        f"  {clinic.get('working_hours_start')}-{clinic.get('working_hours_end')} "
        f"[{clinic.get('working_days')}]"
    )


async def admin_clinics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    clinics = list_clinic_locations(active_only=False)
    if not clinics:
        await update.message.reply_text("Klinikalar ro'yxati bo'sh. /add_clinic bilan qo'shing.")
        return
    lines = [_format_clinic_line(clinic) for clinic in clinics]
    await update.message.reply_text("Klinikalar:\n\n" + "\n\n".join(lines))


async def admin_add_clinic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    if len(context.args) < 1:
        await update.message.reply_text(
            "Foydalanish: /add_clinic <json>\n"
            'Masalan: {"clinic_name":"Boysunov Clinic","staff_name":"Sohibnazar Boysunov",'
            '"role":"doctor","address":"Toshkent","latitude":41.31,"longitude":69.28,'
            '"phone":"+998901234567","specialty":"neurology","services":"MRI, EMG"}'
        )
        return
    try:
        payload = json.loads(" ".join(context.args))
        clinic = create_clinic_location(**payload)
        await update.message.reply_text(
            f"Klinika qo'shildi.\n\n{_format_clinic_line(clinic)}"
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        await update.message.reply_text(f"Xato: {exc}")


async def admin_recommend_clinic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: /recommend_clinic <patient_id> [specialty]")
        return
    patient_id = int(context.args[0])
    specialty = context.args[1] if len(context.args) > 1 else None
    recommendation = recommend_clinic_for_patient(patient_id, specialty=specialty)
    if recommendation is None:
        await update.message.reply_text("Mos klinika topilmadi.")
        return
    await update.message.reply_text(format_clinic_recommendation_message(recommendation))


async def admin_deactivate_clinic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _deny_unless_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: /deactivate_clinic <clinic_id>")
        return
    clinic_id = int(context.args[0])
    clinic = deactivate_clinic_location(clinic_id)
    if clinic is None:
        await update.message.reply_text("Klinika topilmadi.")
        return
    await update.message.reply_text(f"Klinika #{clinic_id} o'chirildi (deaktiv).")

"""Structured appointment booking flow — no AI-generated times."""

from __future__ import annotations

import logging
import re
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from app.consultation_intelligence.conversation_router import is_booking_intent
from app.domain.appointment_status import DEFAULT_DOCTOR_NAME
from app.repositories.appointment_repository import create_appointment
from app.repositories.conversation_repository import save_message
from app.repositories.patient_profile_repository import update_patient_profile
from app.services.appointment_notifications import notify_admins_new_appointment
from app.services.clinic_locator_service import (
    format_clinic_recommendation_message,
    recommend_clinic_for_patient,
)

logger = logging.getLogger("doctor_boysunov.appointments")

BOOKING_STATE_KEY = "appointment_booking"

# Kept for backward compatibility — the actual detection now runs through the
# shared conversation router (app.consultation_intelligence.conversation_router)
# so booking phrases like "book me", "call me", "onlayn konsultatsiya", etc.
# are recognized consistently everywhere in the app.
BOOKING_TRIGGERS = (
    "i want an appointment",
    "navbat olmoqchiman",
    "qabulga yoziling",
)

BOOKING_STEPS = (
    "full_name",
    "phone_number",
    "appointment_date",
    "appointment_time",
    "complaint",
    "confirm",
)

STEP_PROMPTS = {
    "full_name": "Qabulga yozilish uchun to'liq ismingizni yozing:",
    "phone_number": "Telefon raqamingizni yozing:",
    "appointment_date": "Qaysi sanada qabulga kelmoqchisiz? (masalan: 2026-08-01)",
    "appointment_time": "Qaysi vaqtda qabulga kelmoqchisiz? (masalan: 14:00)",
    "complaint": "Asosiy shikoyatingizni qisqacha yozing:",
}

CONFIRM_YES = ("ha", "yes", "tasdiqlayman", "to'g'ri", "togri", "ok")
CONFIRM_NO = ("yo'q", "yoq", "bekor", "cancel", "no")


def is_booking_trigger(text: str) -> bool:
    return is_booking_intent(text)


def _get_booking_state(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
    state = context.user_data.get(BOOKING_STATE_KEY)
    if isinstance(state, dict):
        return state
    return None


def _set_booking_state(context: ContextTypes.DEFAULT_TYPE, state: dict[str, Any]) -> None:
    context.user_data[BOOKING_STATE_KEY] = state


def _clear_booking_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(BOOKING_STATE_KEY, None)


def _start_booking(context: ContextTypes.DEFAULT_TYPE, *, recommendation: dict | None = None) -> str:
    _set_booking_state(
        context,
        {
            "step": "full_name",
            "full_name": None,
            "phone_number": None,
            "appointment_date": None,
            "appointment_time": None,
            "complaint": None,
            "clinic_location_id": recommendation.get("clinic_location_id") if recommendation else None,
            "doctor_name": recommendation.get("staff_name") if recommendation else DEFAULT_DOCTOR_NAME,
            "clinic_name": recommendation.get("clinic_name") if recommendation else None,
        },
    )
    return STEP_PROMPTS["full_name"]


def _build_confirmation_summary(booking: dict[str, Any]) -> str:
    doctor_line = booking.get("doctor_name") or DEFAULT_DOCTOR_NAME
    clinic_line = booking.get("clinic_name") or "Doctor Boysunov Clinic"
    return (
        "Qabul so'rovingiz:\n\n"
        f"Klinika: {clinic_line}\n"
        f"Shifokor: {doctor_line}\n"
        f"Ism: {booking['full_name']}\n"
        f"Telefon: {booking['phone_number']}\n"
        f"Sana: {booking['appointment_date']}\n"
        f"Vaqt: {booking['appointment_time']}\n"
        f"Shikoyat: {booking['complaint']}\n\n"
        "Ma'lumotlar to'g'rimi? Tasdiqlash uchun \"Ha\" yozing yoki bekor qilish uchun \"Bekor\"."
    )


def _normalize_answer(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _is_yes(text: str) -> bool:
    normalized = _normalize_answer(text).lower()
    return normalized in CONFIRM_YES


def _is_no(text: str) -> bool:
    normalized = _normalize_answer(text).lower()
    return normalized in CONFIRM_NO


async def _reply_and_remember(
    update: Update,
    conversation_id: int,
    text: str,
) -> None:
    save_message(conversation_id, "assistant", text)
    await update.message.reply_text(text)


async def start_booking_flow_for_patient(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_id: int,
    conversation_id: int,
) -> None:
    """Kick off the structured booking wizard directly (bypasses trigger-phrase
    detection). Used both by ``handle_appointment_flow`` itself and by the
    conversation router hand-off when a booking intent is detected mid-consultation."""
    recommendation = recommend_clinic_for_patient(user_id)
    prompt = _start_booking(context, recommendation=recommendation)
    save_message(conversation_id, "assistant", prompt)
    await update.message.reply_text(prompt)
    if recommendation is not None:
        clinic_msg = format_clinic_recommendation_message(recommendation)
        save_message(conversation_id, "assistant", clinic_msg)
        await update.message.reply_text(clinic_msg)


async def handle_appointment_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_id: int,
    conversation_id: int,
) -> bool:
    if context is None or context.user_data is None:
        return False

    user_message = update.message.text
    booking = _get_booking_state(context)

    if booking is None:
        if not is_booking_trigger(user_message):
            return False
        await start_booking_flow_for_patient(
            update, context, user_id=user_id, conversation_id=conversation_id
        )
        return True

    step = booking.get("step")
    if step not in BOOKING_STEPS:
        # Defensive state-machine repair: a booking record must always be in a
        # known step. Never silently fall through to `return False` (that
        # would leak the message back into the consultation engine and is
        # exactly the class of bug reported — booking must be a one-way lock
        # until the user explicitly cancels).
        booking["step"] = "full_name"
        _set_booking_state(context, booking)
        await _reply_and_remember(update, conversation_id, STEP_PROMPTS["full_name"])
        return True

    answer = _normalize_answer(user_message)

    if step != "confirm" and _is_no(answer):
        _clear_booking_state(context)
        reply = "Qabulga yozilish bekor qilindi. Yana yozmoqchi bo'lsangiz, \"Navbat olmoqchiman\" deb yozing."
        await _reply_and_remember(update, conversation_id, reply)
        return True

    if step != "confirm" and is_booking_intent(answer) and not _is_yes(answer):
        # State-machine lock: the patient is already inside the booking wizard.
        # If they repeat a booking-intent phrase ("Book me", "Online
        # consultation", "Appointment", ...) instead of answering the current
        # field, do NOT store that phrase as real data (it would corrupt the
        # record with garbage like full_name="Book me") and do NOT fall back
        # to the consultation engine. Stay locked on the same step.
        reply = (
            "Siz allaqachon qabulga yozilish jarayonidasiz — davom etamiz.\n\n"
            f"{STEP_PROMPTS[step]}"
        )
        await _reply_and_remember(update, conversation_id, reply)
        return True

    if step == "full_name":
        if len(answer) < 2:
            reply = "Iltimos, to'liq ismingizni yozing."
            await _reply_and_remember(update, conversation_id, reply)
            return True
        booking["full_name"] = answer
        booking["step"] = "phone_number"
        _set_booking_state(context, booking)
        await _reply_and_remember(update, conversation_id, STEP_PROMPTS["phone_number"])
        return True

    if step == "phone_number":
        digits = re.sub(r"\D", "", answer)
        if len(digits) < 9:
            reply = "Iltimos, to'g'ri telefon raqamini yozing."
            await _reply_and_remember(update, conversation_id, reply)
            return True
        booking["phone_number"] = answer
        booking["step"] = "appointment_date"
        _set_booking_state(context, booking)
        await _reply_and_remember(update, conversation_id, STEP_PROMPTS["appointment_date"])
        return True

    if step == "appointment_date":
        if len(answer) < 3:
            reply = "Iltimos, afzal ko'rgan sanangizni yozing."
            await _reply_and_remember(update, conversation_id, reply)
            return True
        booking["appointment_date"] = answer
        booking["step"] = "appointment_time"
        _set_booking_state(context, booking)
        await _reply_and_remember(update, conversation_id, STEP_PROMPTS["appointment_time"])
        return True

    if step == "appointment_time":
        if len(answer) < 2:
            reply = "Iltimos, afzal ko'rgan vaqtingizni yozing."
            await _reply_and_remember(update, conversation_id, reply)
            return True
        booking["appointment_time"] = answer
        booking["step"] = "complaint"
        _set_booking_state(context, booking)
        await _reply_and_remember(update, conversation_id, STEP_PROMPTS["complaint"])
        return True

    if step == "complaint":
        if len(answer) < 3:
            reply = "Iltimos, shikoyatingizni qisqacha yozing."
            await _reply_and_remember(update, conversation_id, reply)
            return True
        booking["complaint"] = answer
        booking["step"] = "confirm"
        _set_booking_state(context, booking)
        summary = _build_confirmation_summary(booking)
        await _reply_and_remember(update, conversation_id, summary)
        return True

    if step == "confirm":
        if _is_yes(answer):
            patient_profile = update_patient_profile(
                user_id,
                full_name=booking["full_name"],
                phone_number=booking["phone_number"],
            )
            appointment = create_appointment(
                patient_id=user_id,
                doctor_name=booking.get("doctor_name") or DEFAULT_DOCTOR_NAME,
                appointment_date=booking["appointment_date"],
                appointment_time=booking["appointment_time"],
                complaint=booking["complaint"],
                clinic_location_id=booking.get("clinic_location_id"),
            )
            bot = getattr(context, "bot", None)
            if bot is not None:
                await notify_admins_new_appointment(
                    bot,
                    appointment,
                    patient_profile=patient_profile,
                )
            _clear_booking_state(context)
            reply = (
                "Qabul so'rovingiz qabul qilindi.\n\n"
                f"So'rov raqami: {appointment['id']}\n"
                f"Shifokor: {appointment['doctor_name']}\n"
                f"Afzal ko'rgan sana: {appointment['appointment_date']}\n"
                f"Afzal ko'rgan vaqt: {appointment['appointment_time']}\n"
                f"Holat: {appointment['status']}\n\n"
                "Klinika siz bilan bog'lanib, aniq vaqtni tasdiqlaydi."
            )
            await _reply_and_remember(update, conversation_id, reply)
            logger.info(
                "appointment_booked user_id=%s appointment_id=%s",
                user_id,
                appointment["id"],
            )
            return True

        if _is_no(answer):
            _clear_booking_state(context)
            reply = "Qabulga yozilish bekor qilindi."
            await _reply_and_remember(update, conversation_id, reply)
            return True

        reply = "Tasdiqlash uchun \"Ha\" yoki bekor qilish uchun \"Bekor\" deb yozing."
        await _reply_and_remember(update, conversation_id, reply)
        return True

    # Unreachable in practice (all valid BOOKING_STEPS are handled above and
    # unknown steps are repaired earlier), but kept as a last-resort guard
    # that still honors the "never leak back to consultation" lock instead of
    # returning False.
    booking["step"] = "full_name"
    _set_booking_state(context, booking)
    await _reply_and_remember(update, conversation_id, STEP_PROMPTS["full_name"])
    return True

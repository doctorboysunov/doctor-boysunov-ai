"""Patient address and GPS location registration."""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes

from app.repositories.conversation_repository import save_message
from app.repositories.patient_profile_repository import (
    get_patient_profile,
    update_patient_profile,
)
from app.services.location_profile import (
    has_location_stored,
    is_location_update_trigger,
    is_medical_complaint,
    is_skip_answer,
)
from app.services.registration_state import (
    LOCATION_STATE_KEY,
    clear_registration_state,
    get_pending_registration_step,
    get_registration_state,
    pause_registration,
    registration_snapshot,
    resume_registration,
    set_registration_step,
    start_registration,
)

logger = logging.getLogger("doctor_boysunov.location")

SHARE_LOCATION_BUTTON = "📍 Lokatsiyani ulashish"

STEP_PROMPTS = {
    "country": "Ro'yxatdan o'tish: qaysi mamlakatda yashaysiz?",
    "region": "Qaysi viloyat yoki regionda yashaysiz?",
    "district": "Qaysi tumanda yashaysiz?",
    "address": (
        "Uy manzilingizni yozing (ixtiyoriy). "
        "O'tkazib yuborish uchun \"Skip\" deb yozing."
    ),
    "share_location": (
        "Aniqroq joylashuv uchun pastdagi \"Lokatsiyani ulashish\" tugmasini bosing. "
        "GPS koordinatalaringiz saqlanadi. "
        "O'tkazib yuborish uchun \"Skip\" deb yozing."
    ),
}

COMPLETION_MESSAGE = (
    "Manzil ma'lumotlaringiz saqlandi. Endi savollaringizni yozishingiz mumkin."
)


class LocationHandleResult(str, Enum):
    NOT_IN_REGISTRATION = "not_in_registration"
    HANDLED = "handled"
    MEDICAL_PAUSE = "medical_pause"
    COMPLETED = "completed"


def build_share_location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(SHARE_LOCATION_BUTTON, request_location=True)]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )


def _normalize_answer(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def start_location_registration(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    updating: bool = False,
) -> str:
    start_registration(context, updating=updating)
    return STEP_PROMPTS["country"]


async def _reply_and_remember(
    update: Update,
    conversation_id: int,
    text: str,
    *,
    reply_markup=None,
) -> None:
    save_message(conversation_id, "assistant", text)
    kwargs = {}
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup
    await update.message.reply_text(text, **kwargs)


async def _complete_registration(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_id: int,
    conversation_id: int,
    announce: bool = True,
) -> None:
    snapshot_before = registration_snapshot(context)
    clear_registration_state(context)
    logger.info(
        "location_registration_completed user_id=%s before=%s after=%s",
        user_id,
        snapshot_before,
        registration_snapshot(context),
    )
    if announce:
        await _reply_and_remember(
            update,
            conversation_id,
            COMPLETION_MESSAGE,
            reply_markup=ReplyKeyboardRemove(),
        )


async def _maybe_complete_after_required_fields(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_id: int,
    conversation_id: int,
) -> LocationHandleResult | None:
    profile = get_patient_profile(user_id)
    if profile and has_location_stored(profile):
        await _complete_registration(
            update,
            context,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return LocationHandleResult.COMPLETED
    return None


async def handle_location_registration_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_id: int,
    conversation_id: int,
    patient_profile: dict[str, Any],
) -> LocationHandleResult:
    if context is None or context.user_data is None:
        return LocationHandleResult.NOT_IN_REGISTRATION

    user_message = update.message.text or ""
    normalized = _normalize_answer(user_message)

    if is_location_update_trigger(normalized):
        start_registration(context, updating=True)
        await _reply_and_remember(
            update,
            conversation_id,
            STEP_PROMPTS["country"],
            reply_markup=ReplyKeyboardRemove(),
        )
        return LocationHandleResult.HANDLED

    reg_state = get_registration_state(context)
    step = get_pending_registration_step(context)

    if reg_state is None and step is None:
        if has_location_stored(patient_profile):
            return LocationHandleResult.NOT_IN_REGISTRATION
        start_registration(context)
        await _reply_and_remember(
            update,
            conversation_id,
            STEP_PROMPTS["country"],
            reply_markup=ReplyKeyboardRemove(),
        )
        return LocationHandleResult.HANDLED

    profile_now = get_patient_profile(user_id) or patient_profile
    if step in ("address", "share_location") and has_location_stored(profile_now):
        clear_registration_state(context)
        logger.info(
            "registration_auto_finished_required_fields_saved user_id=%s step=%s",
            user_id,
            step,
        )
        return LocationHandleResult.NOT_IN_REGISTRATION

    if reg_state == "paused":
        if is_medical_complaint(normalized):
            logger.info(
                "registration_stays_paused_for_medical user_id=%s step=%s text=%r",
                user_id,
                step,
                normalized[:120],
            )
            return LocationHandleResult.MEDICAL_PAUSE
        resume_registration(context)
        step = get_pending_registration_step(context)
        logger.info(
            "registration_resumed user_id=%s step=%s snapshot=%s",
            user_id,
            step,
            registration_snapshot(context),
        )

    step = get_pending_registration_step(context)
    if step and is_medical_complaint(normalized):
        paused_step = pause_registration(context)
        logger.info(
            "registration_paused_for_medical user_id=%s step=%s snapshot=%s text=%r",
            user_id,
            paused_step,
            registration_snapshot(context),
            normalized[:120],
        )
        return LocationHandleResult.MEDICAL_PAUSE

    if step == "country":
        if len(normalized) < 2:
            await _reply_and_remember(
                update,
                conversation_id,
                "Iltimos, mamlakat nomini yozing.",
            )
            return LocationHandleResult.HANDLED
        update_patient_profile(user_id, country=normalized)
        set_registration_step(context, "region")
        await _reply_and_remember(update, conversation_id, STEP_PROMPTS["region"])
        return LocationHandleResult.HANDLED

    if step == "region":
        if len(normalized) < 2:
            await _reply_and_remember(
                update,
                conversation_id,
                "Iltimos, viloyat yoki region nomini yozing.",
            )
            return LocationHandleResult.HANDLED
        update_patient_profile(user_id, region=normalized, city_region=normalized)
        set_registration_step(context, "district")
        await _reply_and_remember(update, conversation_id, STEP_PROMPTS["district"])
        return LocationHandleResult.HANDLED

    if step == "district":
        if len(normalized) < 2:
            await _reply_and_remember(
                update,
                conversation_id,
                "Iltimos, tuman nomini yozing.",
            )
            return LocationHandleResult.HANDLED
        update_patient_profile(user_id, district=normalized)
        completed = await _maybe_complete_after_required_fields(
            update,
            context,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if completed is not None:
            return completed
        set_registration_step(context, "address")
        await _reply_and_remember(update, conversation_id, STEP_PROMPTS["address"])
        return LocationHandleResult.HANDLED

    if step == "address":
        if not is_skip_answer(normalized):
            update_patient_profile(user_id, address=normalized)
        completed = await _maybe_complete_after_required_fields(
            update,
            context,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if completed is not None:
            return completed
        set_registration_step(context, "share_location")
        await _reply_and_remember(
            update,
            conversation_id,
            STEP_PROMPTS["share_location"],
            reply_markup=build_share_location_keyboard(),
        )
        return LocationHandleResult.HANDLED

    if step == "share_location":
        if is_skip_answer(normalized):
            await _complete_registration(
                update,
                context,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            return LocationHandleResult.COMPLETED
        await _reply_and_remember(
            update,
            conversation_id,
            "Iltimos, \"Lokatsiyani ulashish\" tugmasini bosing yoki \"Skip\" deb yozing.",
            reply_markup=build_share_location_keyboard(),
        )
        return LocationHandleResult.HANDLED

    clear_registration_state(context)
    return LocationHandleResult.NOT_IN_REGISTRATION


async def handle_location_share(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    from app.handlers.common import register_telegram_user
    from app.repositories.conversation_repository import get_or_create_active_conversation

    if update.message is None or update.message.location is None:
        return

    user_id = register_telegram_user(update)
    conversation_id = get_or_create_active_conversation(user_id)
    location = update.message.location

    update_patient_profile(
        user_id,
        latitude=float(location.latitude),
        longitude=float(location.longitude),
    )

    save_message(
        conversation_id,
        "user",
        f"[location shared] latitude={location.latitude}, longitude={location.longitude}",
    )

    step = get_pending_registration_step(context)
    if step == "share_location":
        await _complete_registration(
            update,
            context,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return

    reply = (
        "GPS koordinatalaringiz saqlandi.\n"
        f"Latitude: {location.latitude}\n"
        f"Longitude: {location.longitude}"
    )
    save_message(conversation_id, "assistant", reply)
    await update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
    logger.info(
        "location_shared user_id=%s latitude=%s longitude=%s",
        user_id,
        location.latitude,
        location.longitude,
    )

"""Patient address and GPS location registration."""

from __future__ import annotations

import logging
import re
from typing import Any

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes

from app.repositories.conversation_repository import save_message
from app.repositories.patient_profile_repository import update_patient_profile
from app.services.location_profile import (
    has_location_stored,
    is_skip_answer,
    is_location_update_trigger,
)

logger = logging.getLogger("doctor_boysunov.location")

LOCATION_STATE_KEY = "location_registration"
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


def build_share_location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(SHARE_LOCATION_BUTTON, request_location=True)]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )


def _normalize_answer(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _get_location_state(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
    if context is None or context.user_data is None:
        return None
    state = context.user_data.get(LOCATION_STATE_KEY)
    if isinstance(state, dict):
        return state
    return None


def _set_location_state(context: ContextTypes.DEFAULT_TYPE, state: dict[str, Any]) -> None:
    context.user_data[LOCATION_STATE_KEY] = state


def _clear_location_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context is not None and context.user_data is not None:
        context.user_data.pop(LOCATION_STATE_KEY, None)


def start_location_registration(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    updating: bool = False,
) -> str:
    _set_location_state(
        context,
        {
            "step": "country",
            "updating": updating,
        },
    )
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
) -> None:
    _clear_location_state(context)
    await _reply_and_remember(
        update,
        conversation_id,
        COMPLETION_MESSAGE,
        reply_markup=ReplyKeyboardRemove(),
    )
    logger.info("location_registration_completed user_id=%s", user_id)


async def handle_location_registration_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_id: int,
    conversation_id: int,
    patient_profile: dict[str, Any],
) -> bool:
    if context is None or context.user_data is None:
        return False

    user_message = update.message.text or ""
    normalized = _normalize_answer(user_message)

    if is_location_update_trigger(normalized):
        start_location_registration(context, updating=True)
        await _reply_and_remember(
            update,
            conversation_id,
            STEP_PROMPTS["country"],
            reply_markup=ReplyKeyboardRemove(),
        )
        return True

    state = _get_location_state(context)
    if state is None:
        if has_location_stored(patient_profile):
            return False
        start_location_registration(context)
        await _reply_and_remember(
            update,
            conversation_id,
            STEP_PROMPTS["country"],
            reply_markup=ReplyKeyboardRemove(),
        )
        return True

    step = state.get("step")

    if step == "country":
        if len(normalized) < 2:
            await _reply_and_remember(
                update,
                conversation_id,
                "Iltimos, mamlakat nomini yozing.",
            )
            return True
        update_patient_profile(user_id, country=normalized)
        state["step"] = "region"
        _set_location_state(context, state)
        await _reply_and_remember(update, conversation_id, STEP_PROMPTS["region"])
        return True

    if step == "region":
        if len(normalized) < 2:
            await _reply_and_remember(
                update,
                conversation_id,
                "Iltimos, viloyat yoki region nomini yozing.",
            )
            return True
        update_patient_profile(user_id, region=normalized, city_region=normalized)
        state["step"] = "district"
        _set_location_state(context, state)
        await _reply_and_remember(update, conversation_id, STEP_PROMPTS["district"])
        return True

    if step == "district":
        if len(normalized) < 2:
            await _reply_and_remember(
                update,
                conversation_id,
                "Iltimos, tuman nomini yozing.",
            )
            return True
        update_patient_profile(user_id, district=normalized)
        state["step"] = "address"
        _set_location_state(context, state)
        await _reply_and_remember(update, conversation_id, STEP_PROMPTS["address"])
        return True

    if step == "address":
        if not is_skip_answer(normalized):
            update_patient_profile(user_id, address=normalized)
        state["step"] = "share_location"
        _set_location_state(context, state)
        await _reply_and_remember(
            update,
            conversation_id,
            STEP_PROMPTS["share_location"],
            reply_markup=build_share_location_keyboard(),
        )
        return True

    if step == "share_location":
        if is_skip_answer(normalized):
            await _complete_registration(
                update,
                context,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            return True
        await _reply_and_remember(
            update,
            conversation_id,
            "Iltimos, \"Lokatsiyani ulashish\" tugmasini bosing yoki \"Skip\" deb yozing.",
            reply_markup=build_share_location_keyboard(),
        )
        return True

    _clear_location_state(context)
    return False


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

    state = _get_location_state(context)
    if state is not None and state.get("step") == "share_location":
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

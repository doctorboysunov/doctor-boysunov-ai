import json
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.config import DATABASE_PATH
from app.domain.conversation_flow import mark_consultation_flow, resolve_incoming_message_flow
from app.domain.patient_profile_fields import PROFILE_FIELDS
from app.handlers.appointments import handle_appointment_flow
from app.handlers.common import get_telegram_user_id, register_telegram_user
from app.handlers.location import LocationHandleResult, handle_location_registration_text
from app.handlers.patient_creation_handler import execute_patient_creation_from_text
from app.repositories.conversation_repository import (
    get_last_messages,
    get_or_create_active_conversation,
    save_message,
)
from app.repositories.patient_profile_repository import (
    get_or_create_patient_profile,
    update_patient_profile,
)
from app.services.consultation_engine import (
    process_consultation_turn,
    should_use_consultation_engine,
)
from app.services.location_profile import has_location_stored
from app.services.openai_service import ask_ai
from app.services.profile_extraction import extract_profile_updates
from app.services.routing_trace import ROUTING_FIX_VERSION, RoutingTrace

HISTORY_LIMIT = 10

logger = logging.getLogger("doctor_boysunov.chat")


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message is None or not message.text:
        return
    await process_text_message(
        update,
        context,
        message.text,
        entry_handler="chat.py::chat (MessageHandler TEXT)",
    )


async def process_text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
    *,
    entry_handler: str,
) -> None:
    telegram_id = get_telegram_user_id(update)

    trace = RoutingTrace(
        telegram_id=telegram_id or 0,
        text=user_message or "",
        entry_handler=entry_handler,
    )
    trace.consider("main.py MessageHandler(filters.TEXT & ~filters.COMMAND)")

    if telegram_id is None:
        trace.check(
            location="chat.py",
            condition="telegram_id is not None",
            result=False,
            detail="abort — user unknown",
        )
        trace.select("chat.py early exit", "telegram_id missing")
        trace.dump()
        await update.message.reply_text("Foydalanuvchi aniqlanmadi.")
        return

    trace.check(
        location="chat.py",
        condition="telegram_id is not None",
        result=True,
        detail=f"telegram_id={telegram_id}",
    )

    decision = resolve_incoming_message_flow(telegram_id, user_message, trace=trace)
    logger.info(
        "chat_route telegram_user_id=%s flow=%s is_admin=%s routing_fix=%s text=%r",
        telegram_id,
        decision.flow,
        decision.is_admin,
        ROUTING_FIX_VERSION,
        user_message[:120],
    )

    is_patient_creation = decision.flow == "patient_creation"
    trace.check(
        location="chat.py",
        condition="decision.flow == 'patient_creation'",
        result=is_patient_creation,
        detail=f"flow={decision.flow}",
    )

    if is_patient_creation:
        trace.select("execute_patient_creation_from_text", decision.reason)
        trace.dump()
        await execute_patient_creation_from_text(
            update,
            context,
            text=user_message,
            source="telegram",
            telegram_id=telegram_id,
        )
        return

    trace.consider("register_telegram_user + conversation persistence")
    user_id = register_telegram_user(update)
    conversation_id = get_or_create_active_conversation(user_id)
    save_message(conversation_id, "user", user_message)

    profile_updates = extract_profile_updates(user_message)
    if profile_updates:
        update_patient_profile(user_id, **profile_updates)
        logger.info(
            "patient_profile_updated user_id=%s fields=%s",
            user_id,
            sorted(profile_updates),
        )

    patient_profile = get_or_create_patient_profile(user_id)

    if not decision.is_admin:
        trace.consider("handle_location_registration_text (patient only)")
        location_result = await handle_location_registration_text(
            update,
            context,
            user_id=user_id,
            conversation_id=conversation_id,
            patient_profile=patient_profile,
        )
        location_handled = location_result in (
            LocationHandleResult.HANDLED,
            LocationHandleResult.COMPLETED,
        )
        medical_pause = location_result == LocationHandleResult.MEDICAL_PAUSE
        trace.check(
            location="chat.py",
            condition="location registration result",
            result=location_result.value,
            detail=f"handled={location_handled} medical_pause={medical_pause}",
        )
        if location_handled:
            trace.select("location_registration_handler", "patient location step handled message")
            trace.skip_medical_ai("location registration handler returned early")
            trace.dump()
            return
        if medical_pause:
            trace.select("registration_paused_for_medical", "routing to Medical AI during registration")

        appt_handled = await handle_appointment_flow(
            update,
            context,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        trace.check(
            location="chat.py",
            condition="not is_admin AND handle_appointment_flow returned True",
            result=appt_handled,
            detail="patient appointment booking",
        )
        if appt_handled:
            trace.select("appointment_booking_handler", "appointment flow handled message")
            trace.skip_medical_ai("appointment handler returned early")
            trace.dump()
            return

        patient_profile = get_or_create_patient_profile(user_id)
        has_location = has_location_stored(patient_profile)
        trace.check(
            location="chat.py",
            condition="not is_admin AND has_location_stored(patient_profile)",
            result=has_location,
            detail="patient must share location before AI",
        )
        if not has_location and not medical_pause:
            trace.select("location_gate", "patient has no location — silent return")
            trace.skip_medical_ai("patient location not stored yet")
            trace.dump()
            return
    else:
        trace.check(
            location="chat.py",
            condition="is_admin — skip location gate",
            result=True,
            detail="admin messages never blocked by location registration",
        )
        appt_handled = await handle_appointment_flow(
            update,
            context,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        trace.check(
            location="chat.py",
            condition="is_admin AND handle_appointment_flow returned True",
            result=appt_handled,
            detail="optional admin appointment flow",
        )
        if appt_handled:
            trace.select("appointment_booking_handler", "admin appointment flow handled message")
            trace.skip_medical_ai("appointment handler returned early")
            trace.dump()
            return

    consultation = mark_consultation_flow(decision)
    conversation_mode = "doctor_admin" if decision.is_admin else "patient"
    trace.medical_ai(
        f"conversation_mode={conversation_mode} flow={consultation.flow} reason={consultation.reason}"
    )
    logger.info(
        "chat_medical_ai telegram_user_id=%s conversation_mode=%s flow=%s reason=%s routing_fix=%s",
        telegram_id,
        conversation_mode,
        consultation.flow,
        consultation.reason,
        ROUTING_FIX_VERSION,
    )

    history = get_last_messages(conversation_id, limit=HISTORY_LIMIT)

    user_data = context.user_data if context is not None else None
    use_consultation = (
        not decision.is_admin
        and should_use_consultation_engine(user_id, user_message, user_data)
    )
    if use_consultation:
        trace.select(
            "Professional Consultation Engine",
            f"conversation_mode={conversation_mode} structured medical intake",
        )
        result = process_consultation_turn(
            user_id,
            user_message,
            user_data=user_data,
        )
        save_message(conversation_id, "assistant", result.reply)
        trace.dump()
        await update.message.reply_text(result.reply)
        return

    print("=== BEFORE ask_ai() ===")
    print(f"routing_fix_version={ROUTING_FIX_VERSION}")
    print(f"database={DATABASE_PATH}")
    print(f"conversation_id={conversation_id}")
    print(f"history_count={len(history)}")
    print(f"conversation_mode={conversation_mode}")

    answer = ask_ai(
        history,
        patient_profile=patient_profile,
        conversation_mode=conversation_mode,
    )

    save_message(conversation_id, "assistant", answer)
    trace.dump()
    await update.message.reply_text(answer)

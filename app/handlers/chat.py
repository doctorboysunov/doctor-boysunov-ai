import json
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.config import DATABASE_PATH
from app.domain.admin_conversation_state import (
    cancel_patient_registration,
    get_admin_state,
    registration_mode_active,
)
from app.application.chat.load_conversation_context import load_conversation_context
from app.container import get_container
from app.domain.conversation_flow import mark_consultation_flow, resolve_incoming_message_flow
from app.handlers.appointments import (
    BOOKING_STATE_KEY,
    handle_appointment_flow,
    start_booking_flow_for_patient,
)
from app.handlers.clinic_location_handler import handle_clinic_location_request
from app.handlers.doctor_visit_handler import handle_doctor_visit_message
from app.handlers.pricing_handler import handle_pricing_request
from app.handlers.common import get_telegram_user_id, register_telegram_user
from app.handlers.location import LocationHandleResult, handle_location_registration_text
from app.handlers.patient_creation_handler import execute_patient_creation_from_text
from app.repositories.communication_repository import get_pending_follow_up_reply_delivery
from app.repositories.conversation_repository import (
    get_or_create_active_conversation,
    save_message,
)
from app.repositories.patient_profile_repository import (
    get_or_create_patient_profile,
    update_patient_profile,
)
from app.services.consultation_engine import (
    is_global_emergency_message,
    process_consultation_turn,
    should_use_consultation_engine,
)
from app.services.intent_router import classify_message_intent, log_intent_classification
from app.services.location_profile import is_registration_complete
from app.services.message_dispatcher import resolve_target_module
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
        memory_repo = get_container().memories
        for key, value in profile_updates.items():
            memory_repo.upsert_memory(user_id, key, value)
        logger.info(
            "patient_profile_updated user_id=%s fields=%s",
            user_id,
            sorted(profile_updates),
        )

    patient_profile = get_or_create_patient_profile(user_id)

    if not decision.is_admin:
        # Conversation router state-machine priority order (highest first):
        #   1. Emergency        — a confirmed emergency always wins, even over
        #                         an explicit booking request.
        #   2. Booking          — once booking intent is detected (or a
        #                         booking wizard is already in progress) it is
        #                         a *lock*: every subsequent message routes
        #                         straight into the wizard, ahead of location
        #                         registration and the consultation engine,
        #                         until the patient explicitly cancels.
        #   3. Location registration / consultation (handled further below).
        already_in_booking = bool(
            getattr(context, "user_data", None) and context.user_data.get(BOOKING_STATE_KEY)
        )
        is_emergency_priority = not already_in_booking and is_global_emergency_message(user_message)
        trace.check(
            location="chat.py",
            condition="not is_admin AND is_global_emergency_message (router priority 1)",
            result=is_emergency_priority,
            detail="emergency outranks booking/consultation routing",
        )
        if is_emergency_priority:
            trace.select("emergency_priority_handler", "confirmed emergency red flags — bypass booking gate")
            result = process_consultation_turn(
                user_id,
                user_message,
                user_data=getattr(context, "user_data", None),
            )
            save_message(conversation_id, "assistant", result.reply)
            trace.skip_medical_ai("emergency handled directly")
            trace.dump()
            await update.message.reply_text(result.reply)
            return

        # Booking priority #2 — checked BEFORE location registration so an
        # in-progress (or freshly triggered) booking can never be hijacked by
        # the location-registration step machine or any other gate.
        appt_handled = await handle_appointment_flow(
            update,
            context,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        trace.check(
            location="chat.py",
            condition="not is_admin AND handle_appointment_flow returned True (router priority 2 — booking lock)",
            result=appt_handled,
            detail="patient appointment booking, checked ahead of location registration",
        )
        if appt_handled:
            trace.select("appointment_booking_handler", "appointment flow handled message")
            trace.skip_medical_ai("appointment handler returned early")
            trace.dump()
            return

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

        patient_profile = get_or_create_patient_profile(user_id)
        registration_complete = is_registration_complete(patient_profile)
        trace.check(
            location="chat.py",
            condition="not is_admin AND is_registration_complete(patient_profile)",
            result=registration_complete,
            detail="patient must complete mandatory registration (name, phone, country, region, district) before AI",
        )
        if not registration_complete and not medical_pause:
            trace.select("registration_gate", "patient registration incomplete — silent return")
            trace.skip_medical_ai("patient registration not complete yet")
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

        admin_state = get_admin_state(context, admin_telegram_id=telegram_id)
        admin_active_patient_id = admin_state.patient_id if admin_state else None
        in_patient_registration_mode = registration_mode_active(telegram_id)
        user_data_obj = getattr(context, "user_data", None) if context is not None else None
        in_appointment_booking = bool(user_data_obj and user_data_obj.get(BOOKING_STATE_KEY))

        classification = classify_message_intent(
            user_message,
            is_admin=True,
            admin_active_patient_id=admin_active_patient_id,
            pending_follow_up=False,
            in_patient_registration_mode=in_patient_registration_mode,
        )
        route = resolve_target_module(
            classification,
            is_admin=True,
            admin_active_patient_id=admin_active_patient_id,
            in_appointment_booking=in_appointment_booking,
            in_patient_registration_mode=in_patient_registration_mode,
        )
        log_intent_classification(
            telegram_id=telegram_id,
            text=user_message,
            classification=classification,
            module=route.module,
        )

        if in_patient_registration_mode and route.module != "patient_creation":
            cancel_patient_registration(context, admin_telegram_id=telegram_id)
            logger.info(
                "patient_registration_auto_cancelled telegram_user_id=%s routed_module=%s",
                telegram_id,
                route.module,
            )

        if route.module == "doctor_visit":
            trace.select("doctor_visit_handler", route.reason)
            trace.dump()
            await handle_doctor_visit_message(
                update,
                context,
                text=user_message,
                admin_telegram_id=telegram_id,
            )
            return

        if route.module == "clinic_locator":
            trace.select("clinic_location_handler", route.reason)
            trace.dump()
            patient_id = admin_active_patient_id or user_id
            await handle_clinic_location_request(update, context, patient_id=patient_id)
            return

        if route.module == "pricing_info":
            trace.select("pricing_handler", route.reason)
            trace.dump()
            await handle_pricing_request(update)
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

    conversation_context = load_conversation_context(
        user_id,
        conversation_id=conversation_id,
        history_limit=HISTORY_LIMIT,
    )
    history = conversation_context.history

    user_data = getattr(context, "user_data", None) if context is not None else None
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
        await update.message.reply_text(result.reply)
        if result.wants_booking:
            trace.select(
                "appointment_booking_handoff",
                "consultation engine detected booking intent mid-session",
            )
            trace.dump()
            await start_booking_flow_for_patient(
                update, context, user_id=user_id, conversation_id=conversation_id
            )
            return
        trace.dump()
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
        context_instructions=conversation_context.context_instructions,
        conversation_id=conversation_id,
    )

    save_message(conversation_id, "assistant", answer)
    trace.dump()
    await update.message.reply_text(answer)

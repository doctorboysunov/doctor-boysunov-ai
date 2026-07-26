"""Handle patient replies via AI Care Manager."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.repositories.communication_repository import get_pending_follow_up_reply_delivery
from app.repositories.follow_up_repository import get_follow_up
from app.repositories.patient_profile_repository import get_patient_profile
from app.services.care_manager_service import (
    classify_patient_reply,
    notify_doctor_care_alert,
    patient_acknowledgement,
    record_care_manager_reply,
)
from app.services.clinic_locator_service import (
    format_clinic_recommendation_message,
    recommend_clinic_for_patient,
)
from app.services.communication import record_patient_reply
from app.services.follow_up_messages import messages_contain_prescription_language

logger = logging.getLogger("doctor_boysunov.follow_up_reply")


async def handle_follow_up_patient_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    patient_id: int,
    reply_text: str,
) -> bool:
    """Classify reply, record in EMR, notify doctor when needed."""
    delivery = get_pending_follow_up_reply_delivery(patient_id)
    if delivery is None:
        return False

    record_patient_reply(delivery_id=delivery["id"], reply_text=reply_text)

    follow_up = None
    if delivery.get("source_id"):
        try:
            follow_up = get_follow_up(int(delivery["source_id"]))
        except ValueError:
            follow_up = None

    if follow_up is None:
        return False

    outcome = classify_patient_reply(reply_text)
    record_care_manager_reply(
        follow_up=follow_up,
        reply_text=reply_text,
        outcome=outcome,
        event_date=follow_up["scheduled_date"],
    )

    profile = get_patient_profile(patient_id) or {}
    await notify_doctor_care_alert(
        bot=context.bot,
        patient_id=patient_id,
        follow_up_id=follow_up["id"],
        reply_text=reply_text,
        outcome=outcome,
        patient_name=profile.get("full_name"),
        phone=profile.get("phone_number"),
    )

    logger.info(
        "care_manager_reply_handled patient_id=%s follow_up_id=%s outcome=%s",
        patient_id,
        follow_up["id"],
        outcome,
    )

    if update.message is not None:
        reply = patient_acknowledgement(outcome)
        if outcome == "worse":
            recommendation = recommend_clinic_for_patient(patient_id)
            if recommendation is not None:
                reply = reply + "\n\n" + format_clinic_recommendation_message(recommendation)
        await update.message.reply_text(reply)

    return True


def follow_up_messages_are_safe() -> bool:
    return not messages_contain_prescription_language()

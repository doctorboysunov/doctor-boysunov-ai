"""Send due follow-up notifications to patients."""

from __future__ import annotations

import logging

from telegram import Bot

from app.repositories.follow_up_repository import list_due_follow_ups, mark_follow_up_notified
from app.services.communication import send_patient_message
from app.services.follow_up_planner import schedule_next_recurring_if_missing
from app.services.follow_up_scheduler import to_iso_date

logger = logging.getLogger("doctor_boysunov.follow_up_processor")


async def notify_patient_follow_up(bot: Bot, follow_up: dict) -> bool:
    result = await send_patient_message(
        patient_id=follow_up["patient_id"],
        text=follow_up["invitation_text"],
        source_type="follow_up",
        source_id=str(follow_up["id"]),
        bot=bot,
    )
    if not result.success:
        logger.warning(
            "follow_up_notify_failed follow_up_id=%s patient_id=%s attempted=%s error=%s",
            follow_up["id"],
            follow_up["patient_id"],
            result.attempted_channels,
            result.error_message,
        )
        return False

    mark_follow_up_notified(follow_up["id"])

    if follow_up["sequence_number"] >= 6:
        schedule_next_recurring_if_missing(follow_up["treatment_id"])

    logger.info(
        "follow_up_notified follow_up_id=%s patient_id=%s sequence=%s channel=%s delivery_id=%s",
        follow_up["id"],
        follow_up["patient_id"],
        follow_up["sequence_number"],
        result.channel,
        result.delivery_id,
    )
    return True


async def process_due_follow_ups(bot: Bot, *, as_of_date: str | None = None) -> int:
    from datetime import date

    check_date = as_of_date or to_iso_date(date.today())
    due_items = list_due_follow_ups(as_of_date=check_date)
    sent = 0
    for follow_up in due_items:
        if await notify_patient_follow_up(bot, follow_up):
            sent += 1
    return sent

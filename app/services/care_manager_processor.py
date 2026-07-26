"""Process no-response follow-ups — retry then mark."""

from __future__ import annotations

import logging

from telegram import Bot

from app.repositories.follow_up_repository import (
    increment_follow_up_retry,
    list_follow_ups_needing_retry,
)
from app.services.care_manager_service import record_no_response
from app.services.follow_up_messages import build_care_manager_message
from app.services.follow_up_processor import notify_patient_follow_up
from app.services.follow_up_scheduler import to_iso_date

logger = logging.getLogger("doctor_boysunov.care_manager_processor")


async def process_care_manager_no_responses(bot: Bot, *, as_of_date: str | None = None) -> dict[str, int]:
    """Retry unanswered follow-ups after 2 days; mark no_response after second attempt."""
    from datetime import date

    check_date = as_of_date or to_iso_date(date.today())
    candidates = list_follow_ups_needing_retry(as_of_date=check_date)

    retried = 0
    marked_no_response = 0

    for follow_up in candidates:
        if follow_up["retry_count"] >= 1:
            record_no_response(follow_up=follow_up, event_date=check_date)
            marked_no_response += 1
            logger.info(
                "care_manager_no_response patient_id=%s follow_up_id=%s",
                follow_up["patient_id"],
                follow_up["id"],
            )
            continue

        retry_message = build_care_manager_message(
            follow_up["follow_up_kind"],
            sequence_number=follow_up["sequence_number"],
            scheduled_date=follow_up["scheduled_date"],
            is_retry=True,
        )
        follow_up = increment_follow_up_retry(follow_up["id"])
        follow_up = {**follow_up, "invitation_text": retry_message}

        if await notify_patient_follow_up(bot, follow_up):
            retried += 1

    return {"retried": retried, "marked_no_response": marked_no_response}

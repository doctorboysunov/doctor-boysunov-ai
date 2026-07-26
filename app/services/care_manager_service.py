"""AI Care Manager — classify replies, record outcomes, monitor patients."""

from __future__ import annotations

import logging
import re
from typing import Literal

from app.repositories.care_manager_repository import add_care_manager_record
from app.repositories.follow_up_repository import record_follow_up_outcome
from app.services.admin_auth import get_all_admin_telegram_ids
from app.services.follow_up_messages import care_event_type_for_follow_up

logger = logging.getLogger("doctor_boysunov.care_manager")

CareClassification = Literal["good", "no_change", "worse"]

GOOD_PATTERNS = (
    r"yaxshi",
    r"yaxshil",
    r"kamay",
    r"og'riq\s+yo'?q",
    r"better",
    r"improv",
    r"rahmat.*yaxshi",
    r"o'?zgarish\s+yaxshi",
)

NO_CHANGE_PATTERNS = (
    r"o'?zgarmadi",
    r"bir\s+xil",
    r"same",
    r"no\s+change",
    r"hech\s+narsa",
    r"baribir",
)

WORSE_PATTERNS = (
    r"yomonlash",
    r"og'irroq",
    r"kuchay",
    r"wors",
    r"betta",
    r"qo'pollash",
    r"hushim\s+yo'?q",
    r"hush\s+yo'?q",
    r"qon",
    r"ko'krak\s+qisish",
    r"nafas\s+qis",
    r"shoshilinch",
    r"og'riyapti",
    r"og'riydi",
)


def classify_patient_reply(text: str) -> CareClassification:
    lowered = text.lower().strip()
    if any(re.search(pattern, lowered) for pattern in WORSE_PATTERNS):
        return "worse"
    if any(re.search(pattern, lowered) for pattern in NO_CHANGE_PATTERNS):
        return "no_change"
    if any(re.search(pattern, lowered) for pattern in GOOD_PATTERNS):
        return "good"
    # Default: neutral/unclear replies treated as no change — doctor should know.
    return "no_change"


def record_care_manager_send(
    *,
    follow_up: dict,
    message_text: str,
    event_date: str,
    is_retry: bool = False,
) -> dict:
    event_type = "retry_sent" if is_retry else care_event_type_for_follow_up(
        follow_up["follow_up_kind"],
        follow_up["sequence_number"],
    )
    return add_care_manager_record(
        patient_id=follow_up["patient_id"],
        follow_up_id=follow_up["id"],
        sequence_number=follow_up["sequence_number"],
        event_type=event_type,
        outcome="pending",
        message_text=message_text,
        event_date=event_date,
    )


def record_care_manager_reply(
    *,
    follow_up: dict,
    reply_text: str,
    outcome: CareClassification,
    event_date: str,
) -> dict:
    updated = record_follow_up_outcome(
        follow_up["id"],
        outcome=outcome,
        reply_text=reply_text,
        high_priority=(outcome == "worse"),
    )
    record = add_care_manager_record(
        patient_id=follow_up["patient_id"],
        follow_up_id=follow_up["id"],
        sequence_number=follow_up["sequence_number"],
        event_type="reply_received",
        outcome=outcome,
        reply_text=reply_text,
        event_date=event_date,
    )
    logger.info(
        "care_manager_reply patient_id=%s follow_up_id=%s outcome=%s",
        follow_up["patient_id"],
        follow_up["id"],
        outcome,
    )
    return {"follow_up": updated, "record": record}


def record_no_response(*, follow_up: dict, event_date: str) -> dict:
    from app.repositories.follow_up_repository import mark_follow_up_no_response

    updated = mark_follow_up_no_response(follow_up["id"])
    record = add_care_manager_record(
        patient_id=follow_up["patient_id"],
        follow_up_id=follow_up["id"],
        sequence_number=follow_up["sequence_number"],
        event_type="no_response_marked",
        outcome="no_response",
        event_date=event_date,
    )
    return {"follow_up": updated, "record": record}


async def notify_doctor_care_alert(
    *,
    bot,
    patient_id: int,
    follow_up_id: int,
    reply_text: str,
    outcome: CareClassification,
    patient_name: str | None = None,
    phone: str | None = None,
) -> None:
    if outcome == "good":
        return

    if outcome == "worse":
        headline = "⚠️ HIGH PRIORITY: Patient worsening"
        action = "Recommend booking a consultation immediately."
    else:
        headline = "ℹ️ Patient reports no change"
        action = "Review patient status when convenient."

    message = (
        f"{headline}\n\n"
        f"Patient: {patient_name or f'#{patient_id}'}\n"
        f"ID: {patient_id}\n"
        f"Phone: {phone or '—'}\n"
        f"Follow-up ID: {follow_up_id}\n"
        f"Outcome: {outcome.upper()}\n\n"
        f"Reply: {reply_text[:500]}\n\n"
        f"{action}\n"
        "Do not prescribe via bot."
    )
    for admin_id in get_all_admin_telegram_ids():
        try:
            await bot.send_message(chat_id=admin_id, text=message)
        except Exception as exc:  # noqa: BLE001
            logger.warning("care_manager_doctor_alert_failed admin_id=%s error=%s", admin_id, exc)

    add_care_manager_record(
        patient_id=patient_id,
        follow_up_id=follow_up_id,
        sequence_number=None,
        event_type="doctor_notified",
        outcome=outcome,
        message_text=message,
        event_date=event_date_today(),
    )


def event_date_today() -> str:
    from app.services.appointment_dates import clinic_today_iso

    return clinic_today_iso()


def patient_acknowledgement(outcome: CareClassification) -> str:
    if outcome == "good":
        return (
            "Rahmat! Yaxshilanish qayd etildi. Nazorat jadvali davom etadi.\n\n"
            "Eslatma: men dori-darmon yoki retsept bera olmayman."
        )
    if outcome == "worse":
        return (
            "Xabaringiz qabul qilindi. Holatingiz yomonlashgani shifokorga yetkazildi.\n\n"
            "Iltimos, tezroq qabulga yoziling — \"Navbat olmoqchiman\" deb yozing.\n\n"
            "Eslatma: men dori-darmon yoki retsept bera olmayman."
        )
    return (
        "Rahmat, javobingiz qayd etildi. Shifokor holatingizni ko'rib chiqadi.\n\n"
        "Eslatma: men dori-darmon yoki retsept bera olmayman."
    )

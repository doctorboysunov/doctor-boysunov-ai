"""AI Care Manager messages — sequence-specific, no prescriptions."""

from __future__ import annotations

import re

from app.domain.follow_up_schedule import FOLLOW_UP_KINDS

CHECK_IN_MESSAGE = (
    "Assalomu alaykum. Doctor Boysunov AI.\n"
    "Bugungi holatingiz qanday? Og'riq kamayganmi?"
)

MONTH_3_EXAMINATION_MESSAGE = (
    "Assalomu alaykum. Doctor Boysunov AI.\n\n"
    "Davolanishingizdan 3 oy o'tdi. Sizni qayta ko'rikka taklif qilamiz.\n\n"
    "Qabulga yozilish uchun \"Navbat olmoqchiman\" deb yozing."
)

MONTH_6_PREVENTIVE_MESSAGE = (
    "Assalomu alaykum. Doctor Boysunov AI.\n\n"
    "Davolanishingizdan 6 oy o'tdi. Sizni profilaktik davolanish va ko'rikka taklif qilamiz.\n\n"
    "Qabulga yozilish uchun \"Navbat olmoqchiman\" deb yozing."
)

RECURRING_PREVENTIVE_MESSAGE = (
    "Assalomu alaykum. Doctor Boysunov AI.\n\n"
    "Navbatdagi profilaktik ko'rik va davolanish vaqti keldi.\n\n"
    "Qabulga yozilish uchun \"Navbat olmoqchiman\" deb yozing."
)

CARE_MANAGER_RETRY_PREFIX = (
    "Eslatma (Doctor Boysunov AI):\n"
    "Avvalgi xabarga javob olmadik. Bugungi holatingiz qanday?"
)

_PRESCRIPTION_OFFER_PATTERNS = (
    r"\bretsept\s+yoz",
    r"\b\d+\s*mg\b",
    r"\bdori\s+ich",
    r"\btablet",
    r"\bprescri",
)


def build_care_manager_message(
    kind: str,
    *,
    sequence_number: int,
    scheduled_date: str,
    is_retry: bool = False,
) -> str:
    if kind not in FOLLOW_UP_KINDS:
        raise ValueError(f"Unknown follow-up kind: {kind!r}")

    if kind == "check_in" and sequence_number in {1, 2, 3}:
        base = CHECK_IN_MESSAGE
    elif kind == "examination" or sequence_number == 4:
        base = MONTH_3_EXAMINATION_MESSAGE
    elif kind == "preventive" and sequence_number == 5:
        base = MONTH_6_PREVENTIVE_MESSAGE
    elif kind == "preventive":
        base = RECURRING_PREVENTIVE_MESSAGE
    else:
        base = CHECK_IN_MESSAGE

    if is_retry:
        base = f"{CARE_MANAGER_RETRY_PREFIX}\n\n{base}"

    return (
        f"{base}\n\n"
        f"Nazorat raqami: {sequence_number}\n"
        f"Reja sanasi: {scheduled_date}"
    )


def build_follow_up_message(
    kind: str,
    *,
    sequence_number: int,
    scheduled_date: str,
    is_retry: bool = False,
) -> str:
    """Backward-compatible alias for care manager messages."""
    return build_care_manager_message(
        kind,
        sequence_number=sequence_number,
        scheduled_date=scheduled_date,
        is_retry=is_retry,
    )


def care_event_type_for_follow_up(kind: str, sequence_number: int) -> str:
    if kind == "check_in":
        return "check_in_sent"
    if kind == "examination" or sequence_number == 4:
        return "examination_invite"
    return "preventive_invite"


def messages_contain_prescription_language() -> bool:
    combined = " ".join(
        (
            CHECK_IN_MESSAGE,
            MONTH_3_EXAMINATION_MESSAGE,
            MONTH_6_PREVENTIVE_MESSAGE,
            RECURRING_PREVENTIVE_MESSAGE,
            CARE_MANAGER_RETRY_PREFIX,
        )
    ).lower()
    return any(re.search(pattern, combined) for pattern in _PRESCRIPTION_OFFER_PATTERNS)

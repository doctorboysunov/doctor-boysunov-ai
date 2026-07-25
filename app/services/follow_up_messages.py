"""Template messages for follow-ups — no prescriptions, no AI."""

import re

from app.domain.follow_up_schedule import FOLLOW_UP_KINDS

FOLLOW_UP_MESSAGES = {
    "check_in": (
        "Nazorat xabari (Doctor Boysunov AI):\n\n"
        "Davolanish jarayoningiz bo'yicha qisqa nazorat vaqti keldi. "
        "Bugun sog'ligingiz qanday ekanini qisqacha yozing.\n\n"
        "Eslatma: men dori-darmon yoki retsept bera olmayman. "
        "Aniq tavsiya uchun shifokor ko'rigiga murojaat qiling."
    ),
    "examination": (
        "Qayta ko'rik taklifi (Doctor Boysunov klinikasi):\n\n"
        "Davolanishingizdan keyingi nazorat jadvaliga ko'ra sizni "
        "qayta ko'rikka taklif qilamiz.\n\n"
        "Qabulga yozilish uchun \"Navbat olmoqchiman\" deb yozing."
    ),
    "preventive": (
        "Profilaktik davolanish va ko'rik taklifi (Doctor Boysunov klinikasi):\n\n"
        "Sizni profilaktik davolanish va ko'rikka taklif qilamiz.\n\n"
        "Qabulga yozilish uchun \"Navbat olmoqchiman\" deb yozing."
    ),
}

_PRESCRIPTION_OFFER_PATTERNS = (
    r"\bretsept\s+yoz",
    r"\b\d+\s*mg\b",
    r"\bdori\s+ich",
    r"\btablet",
    r"\bprescri",
)


def build_follow_up_message(kind: str, *, sequence_number: int, scheduled_date: str) -> str:
    if kind not in FOLLOW_UP_KINDS:
        raise ValueError(f"Unknown follow-up kind: {kind!r}")

    base = FOLLOW_UP_MESSAGES[kind]
    return (
        f"{base}\n\n"
        f"Nazorat raqami: {sequence_number}\n"
        f"Reja sanasi: {scheduled_date}"
    )


def messages_contain_prescription_language() -> bool:
    combined = " ".join(FOLLOW_UP_MESSAGES.values()).lower()
    return any(re.search(pattern, combined) for pattern in _PRESCRIPTION_OFFER_PATTERNS)

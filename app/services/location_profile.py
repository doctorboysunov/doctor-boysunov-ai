"""Location field helpers for patient profiles."""

from typing import Any

LOCATION_FIELDS = (
    "country",
    "region",
    "district",
    "address",
    "latitude",
    "longitude",
)

LOCATION_UPDATE_TRIGGERS = (
    "manzilni yangilash",
    "update my address",
    "manzilimni o'zgartirish",
    "manzilimni ozgartirish",
)

SKIP_WORDS = ("skip", "o'tkazib yuborish", "otkazib yuborish", "-", "yo'q", "yoq", "tayyor")

_MEDICAL_HINTS = (
    "og'ri",
    "ogri",
    "og‘ri",
    "og'riyapti",
    "ogriyapti",
    "hurts",
    "hurt",
    "pain",
    "ache",
    "shikoyat",
    "symptom",
    "bosh",
    "bel",
    "head",
    "qorin",
    "ko'krak",
    "ko‘krak",
    "tashxis",
    "diagnoz",
    "diagnosis",
    "davolash",
    "treatment",
    "dori",
    "tabletka",
    "tekshiruv",
    "examination",
    "mrt",
    "emg",
    "yomon",
    "worse",
    "better",
    "yaxshi",
    "nima qilay",
    "nima qilish",
    "what should i do",
    "uvish",
    "uvishmoqda",
    "numb",
    "tingling",
    "qo'l",
    "qol",
    "belim",
    "bel ",
)


def is_skip_answer(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in SKIP_WORDS


def is_location_update_trigger(text: str) -> bool:
    normalized = text.strip().lower()
    return any(trigger in normalized for trigger in LOCATION_UPDATE_TRIGGERS)


def is_medical_complaint(text: str | None) -> bool:
    """True when message looks like a symptom / medical question during registration."""
    normalized = (text or "").strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    return any(hint in lowered for hint in _MEDICAL_HINTS)


def has_location_stored(profile: dict[str, Any] | None) -> bool:
    if not profile:
        return False
    return bool(
        profile.get("country")
        and profile.get("region")
        and profile.get("district")
    )


# Mandatory patient registration, in required order: full name and phone
# number are collected before any location fields. A medical consultation
# (or the location-registration step machine) is only considered "done"
# once every one of these is on file.
REQUIRED_REGISTRATION_FIELDS: tuple[str, ...] = (
    "full_name",
    "phone_number",
    "country",
    "region",
    "district",
)


def is_registration_complete(profile: dict[str, Any] | None) -> bool:
    if not profile:
        return False
    return all(profile.get(field) for field in REQUIRED_REGISTRATION_FIELDS)


def first_missing_registration_field(profile: dict[str, Any] | None) -> str | None:
    profile = profile or {}
    for field in REQUIRED_REGISTRATION_FIELDS:
        if not profile.get(field):
            return field
    return None


def format_coordinates(profile: dict[str, Any]) -> str | None:
    latitude = profile.get("latitude")
    longitude = profile.get("longitude")
    if latitude is None or longitude is None:
        return None
    return f"{latitude}, {longitude}"

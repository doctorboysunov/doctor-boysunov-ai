"""Build structured patient profile context for OpenAI requests."""

from typing import Any

from app.domain.patient_profile_fields import PROFILE_CONTEXT_FIELDS

PROFILE_LABELS = {
    "full_name": "full_name",
    "age": "age",
    "sex": "sex",
    "height_cm": "height_cm",
    "weight_kg": "weight_kg",
    "phone_number": "phone_number",
    "city_region": "city_region",
    "address": "address",
    "occupation": "occupation",
    "allergies": "allergies",
    "chronic_diseases": "chronic_diseases",
    "emergency_contact": "emergency_contact",
}


def profile_has_facts(profile: dict[str, Any] | None) -> bool:
    if not profile:
        return False
    return any(profile.get(field) for field in PROFILE_CONTEXT_FIELDS)


def build_profile_instructions(profile: dict[str, Any] | None) -> str | None:
    if not profile_has_facts(profile):
        return None

    lines = [
        "Permanent patient profile (structured facts, separate from chat history):",
        "Use these as already-known patient facts.",
        "Do not ask the patient to repeat information that is already filled in below.",
    ]
    for field in PROFILE_CONTEXT_FIELDS:
        label = PROFILE_LABELS[field]
        value = profile.get(field)
        if value is not None and value != "":
            lines.append(f"- {label}: {value}")

    return "\n".join(lines)

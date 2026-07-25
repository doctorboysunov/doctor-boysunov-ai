"""Build structured patient profile context for OpenAI requests."""

from typing import Any

from app.domain.patient_profile_fields import (
    LOCATION_CONTEXT_FIELDS,
    PROFILE_CONTEXT_FIELDS,
)
from app.services.location_profile import format_coordinates

PROFILE_LABELS = {
    "full_name": "full_name",
    "age": "age",
    "sex": "sex",
    "height_cm": "height_cm",
    "weight_kg": "weight_kg",
    "phone_number": "phone_number",
    "country": "country",
    "region": "region",
    "district": "district",
    "city_region": "city_region",
    "address": "address",
    "latitude": "latitude",
    "longitude": "longitude",
    "occupation": "occupation",
    "allergies": "allergies",
    "chronic_diseases": "chronic_diseases",
    "emergency_contact": "emergency_contact",
}


def profile_has_facts(profile: dict[str, Any] | None) -> bool:
    if not profile:
        return False
    return any(profile.get(field) for field in PROFILE_CONTEXT_FIELDS)


def _append_field_lines(lines: list[str], profile: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        label = PROFILE_LABELS[field]
        value = profile.get(field)
        if value is not None and value != "":
            lines.append(f"- {label}: {value}")


def build_profile_instructions(profile: dict[str, Any] | None) -> str | None:
    if not profile_has_facts(profile):
        return None

    lines = [
        "Permanent patient profile (structured facts, separate from chat history):",
        "Use these as already-known patient facts.",
        "Do not ask the patient to repeat information that is already filled in below.",
    ]

    non_location_fields = tuple(
        field for field in PROFILE_CONTEXT_FIELDS if field not in LOCATION_CONTEXT_FIELDS
    )
    _append_field_lines(lines, profile, non_location_fields)

    location_lines: list[str] = []
    _append_field_lines(location_lines, profile, LOCATION_CONTEXT_FIELDS)
    coordinates = format_coordinates(profile)
    if coordinates:
        location_lines.append(f"- coordinates: {coordinates}")

    if location_lines:
        lines.append("")
        lines.append("Patient location (always use for local medical context):")
        lines.extend(location_lines)

    return "\n".join(lines)

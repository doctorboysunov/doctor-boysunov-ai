"""Detect missing clinical information required for physician-level reasoning."""

from __future__ import annotations

import re
from typing import Any

# High-yield clinical elements by interview phase
_CORE_FIELDS: tuple[tuple[str, str, float], ...] = (
    ("onset_timing", r"qachon|kun|hafta|soat|boshlandi|oldin|duration", 0.95),
    ("symptom_character", r"og['']?riq|xarakter|qanday|pulsatsiya|siquvchi|kuchli", 0.85),
    ("severity_progression", r"juda|yengil|kuchay|kamay|progress|birdan|asta", 0.8),
    ("associated_symptoms", r"ham|bilan|qusish|isitma|nafas|bosh|qorin|titroq", 0.75),
    ("red_flag_screen", r"103|hush|nafas qis|qon|eng kuchli|birdan|kuchsiz", 0.9),
    ("past_history", r"avval|surunkali|diabet|astma|operatsiya|dori|tabletka", 0.65),
    ("pregnancy_status", r"homilador|homiladorlik|menstruatsiya", 0.85),
    ("exertional_trigger", r"yugur|zina|harakat|charchaganda|dam olganda", 0.8),
    ("radiation_pattern", r"tarqal|chap qo['']?l|yelka|jag|orqa", 0.85),
    ("neuro_deficit", r"kuchsiz|uvish|nutq|ko['']?rmay|yurish|muvozanat", 0.85),
)

_EMERGENCY_REQUIRED = ("onset_timing", "red_flag_screen", "severity_progression")
_ROUTINE_REQUIRED = ("onset_timing", "symptom_character", "associated_symptoms")


def _normalize(text: str) -> str:
    return text.lower().replace("'", "'").replace("'", "'")


def _field_present(field: str, pattern: str, combined: str, answered_topics: list[str]) -> bool:
    if field in answered_topics:
        return True
    return bool(re.search(pattern, combined, re.I))


def detect_missing_clinical_information(
    *,
    patient_text: str,
    answered_topics: list[str],
    contradictions: list[str],
    is_emergency: bool,
    is_pregnant: bool = False,
    primary_specialty: str = "",
    model_missing: list[str] | None = None,
) -> list[str]:
    """Return prioritized list of missing high-yield clinical information."""
    combined = _normalize(patient_text)
    missing: list[str] = []
    seen: set[str] = set()

    required = _EMERGENCY_REQUIRED if is_emergency else _ROUTINE_REQUIRED

    field_labels = {
        "onset_timing": "Onset and duration — when symptoms started and how they evolved",
        "symptom_character": "Symptom character — quality, location, pattern",
        "severity_progression": "Severity and progression — better, worse, or stable",
        "associated_symptoms": "Associated symptoms — fever, vomiting, dyspnea, etc.",
        "red_flag_screen": "Red flag screen — emergency features not yet clarified",
        "past_history": "Relevant past history and medications",
        "pregnancy_status": "Pregnancy status (if applicable)",
        "exertional_trigger": "Exertional trigger — symptoms with activity vs rest",
        "radiation_pattern": "Radiation pattern — where pain/symptoms spread",
        "neuro_deficit": "Neurological deficit — weakness, speech, vision, balance",
    }

    for field in required:
        pattern = next(p for f, p, _ in _CORE_FIELDS if f == field)
        if not _field_present(field, pattern, combined, answered_topics):
            label = field_labels.get(field, field)
            if label not in seen:
                missing.append(label)
                seen.add(label)

    # Specialty-specific gaps
    if primary_specialty in {"cardiology", "emergency_medicine"}:
        for field in ("exertional_trigger", "radiation_pattern"):
            pattern = next(p for f, p, _ in _CORE_FIELDS if f == field)
            if not _field_present(field, pattern, combined, answered_topics):
                label = field_labels[field]
                if label not in seen:
                    missing.append(label)
                    seen.add(label)

    if primary_specialty == "neurology":
        field = "neuro_deficit"
        pattern = next(p for f, p, _ in _CORE_FIELDS if f == field)
        if not _field_present(field, pattern, combined, answered_topics):
            label = field_labels[field]
            if label not in seen:
                missing.append(label)
                seen.add(label)

    if is_pregnant and not _field_present("pregnancy_status", _CORE_FIELDS[6][1], combined, answered_topics):
        label = field_labels["pregnancy_status"]
        if label not in seen:
            missing.append(label)
            seen.add(label)

    if contradictions:
        label = "Clarify contradictions in patient story"
        if label not in seen:
            missing.insert(0, label)
            seen.add(label)

    # Merge model-detected gaps (deduplicated)
    for item in model_missing or []:
        item = str(item).strip()
        if item and item not in seen:
            missing.append(item)
            seen.add(item)

    return missing[:8]

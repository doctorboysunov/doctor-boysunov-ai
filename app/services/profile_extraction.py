"""Extract permanent profile updates from Uzbek user messages."""

from __future__ import annotations

import re
from typing import Any

from app.domain.patient_profile_fields import PROFILE_FIELDS

QUESTION_WORDS = {"kim", "nima", "qanday", "qayerda", "qachon", "necha", "ne"}


def _clean_text(value: str) -> str:
    text = value.strip().strip(".!?")
    text = re.sub(r"\s+", " ", text)
    return text


def _is_question_name(value: str, original_message: str) -> bool:
    cleaned = _clean_text(value).lower()
    if cleaned in QUESTION_WORDS:
        return True
    if original_message.rstrip().endswith("?") and cleaned in QUESTION_WORDS:
        return True
    return False


def extract_profile_updates(message: str) -> dict[str, Any]:
    """Return profile field updates detected in a user message."""
    text = message.strip()
    if not text:
        return {}

    updates: dict[str, Any] = {}

    name_patterns = [
        r"(?i)mening ismim\s+(.+)",
        r"(?i)ismim\s+(.+)",
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            candidate = _clean_text(match.group(1))
            if not _is_question_name(candidate, text):
                updates["full_name"] = candidate
            break

    age_match = re.search(r"(?i)men\s+(\d{1,3})\s*yoshdaman", text)
    if age_match:
        updates["age"] = int(age_match.group(1))

    height_match = re.search(
        r"(?i)(?:bo['']?yim|mening bo['']?yim)\s+(\d{2,3})\s*(?:sm|santimetr)",
        text,
    )
    if height_match:
        updates["height_cm"] = int(height_match.group(1))

    weight_match = re.search(
        r"(?i)(?:vaznim|mening vaznim)\s+(\d{2,3})\s*(?:kg|kilogramm)?",
        text,
    )
    if weight_match:
        updates["weight_kg"] = int(weight_match.group(1))

    region_match = re.search(r"(?i)men\s+([A-Za-zÀ-ÿ'-]+?)danman", text)
    if region_match:
        region_value = _clean_text(region_match.group(1))
        updates["city_region"] = region_value
        updates["region"] = region_value

    address_patterns = [
        r"(?i)manzilim\s+(.+)",
        r"(?i)men\s+(.+?)\s+da yashayman",
        r"(?i)yashash manzilim\s+(.+)",
    ]
    for pattern in address_patterns:
        match = re.search(pattern, text)
        if match:
            updates["address"] = _clean_text(match.group(1))
            break

    occupation_patterns = [
        r"(?i)kasbim\s+(.+)",
        r"(?i)men\s+(.+?)\s*bo['']?lib ishlayman",
    ]
    for pattern in occupation_patterns:
        match = re.search(pattern, text)
        if match:
            updates["occupation"] = _clean_text(match.group(1))
            break

    if re.search(r"(?i)men\s+erkakman", text):
        updates["sex"] = "male"
    elif re.search(r"(?i)men\s+ayolman", text):
        updates["sex"] = "female"

    phone_match = re.search(
        r"(?i)(?:telefon(?:im)?|raqamim|telefon raqamim)\s*[:+]?\s*(\+?\d[\d\s-]{8,})",
        text,
    )
    if phone_match:
        phone = re.sub(r"\s+", "", phone_match.group(1))
        if phone.startswith("998"):
            phone = f"+{phone}"
        updates["phone_number"] = phone
    else:
        bare_phone = re.search(r"(\+998\d{9})", text)
        if bare_phone:
            updates["phone_number"] = bare_phone.group(1)

    menda_allergy = re.search(r"(?i)menda\s+(.+?)\s*allergiyam bor", text)
    if menda_allergy:
        allergen = _clean_text(menda_allergy.group(1))
        if allergen.endswith("ka") and len(allergen) > 2:
            allergen = allergen[:-2].strip()
        updates["allergies"] = allergen
    else:
        men_allergy = re.search(r"(?i)men\s+(.+?)(?:ga|ka)\s+allergiyaman", text)
        if men_allergy:
            updates["allergies"] = _clean_text(men_allergy.group(1))
        else:
            allergy_match = re.search(r"(?i)^allergiyam\s+(.+)", text)
            if allergy_match:
                updates["allergies"] = _clean_text(allergy_match.group(1))

    chronic_patterns = [
        r"(?i)surunkali kasalligim\s+(.+)",
        r"(?i)menda\s+(diabet|gipertoniya|astma|yurak kasalligi)\s+bor",
        r"(?i)surunkali\s+(.+?)\s+kasalligim bor",
    ]
    for pattern in chronic_patterns:
        match = re.search(pattern, text)
        if match:
            updates["chronic_diseases"] = _clean_text(match.group(1))
            break

    emergency_match = re.search(
        r"(?i)(?:favqulodda (?:aloqa|kontakt)|qarindoshim)\s*[:\-]?\s*(.+)",
        text,
    )
    if emergency_match:
        updates["emergency_contact"] = _clean_text(emergency_match.group(1))

    if "full_name" not in updates:
        generic_name = re.search(r"(?i)^men\s+([A-Za-zÀ-ÿ'-]{2,})man$", text)
        if generic_name and not re.search(r"(dan|yosh)man$", text, re.I):
            updates["full_name"] = _clean_text(generic_name.group(1))

    return {key: value for key, value in updates.items() if key in PROFILE_FIELDS and value}

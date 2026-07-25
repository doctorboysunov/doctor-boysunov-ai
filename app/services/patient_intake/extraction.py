"""Extract patient name and phone from text."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from openai import OpenAI

from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.services.patient_intake.phone import normalize_phone

client = OpenAI(api_key=OPENAI_API_KEY)

PHONE_PATTERN = re.compile(
    r"(?:(?:\+?998|8)?[\s-]?)?(\d{2})[\s-]?(\d{3})[\s-]?(\d{2})[\s-]?(\d{2})"
)


@dataclass(frozen=True)
class ExtractedPatient:
    full_name: str
    phone_number: str


def clean_name(value: str) -> str:
    name = re.sub(r"\s+", " ", value.strip(" .,:;"))
    return name


def extract_patient_from_text(text: str) -> ExtractedPatient | None:
    stripped = text.strip()
    if not stripped:
        return None

    match = PHONE_PATTERN.search(stripped)
    if not match:
        return None

    raw_phone = match.group(0)
    try:
        phone_number = normalize_phone(raw_phone)
    except ValueError:
        return None

    name_part = stripped[: match.start()].strip(" .,:;-")
    name_part = re.sub(r"(?i)(phone|telefon|tel|raqam)[\s:.-]*$", "", name_part).strip()
    if not name_part:
        return None

    full_name = clean_name(name_part)
    if len(full_name) < 2:
        return None

    return ExtractedPatient(full_name=full_name, phone_number=phone_number)


def extract_patient_with_ai(text: str) -> ExtractedPatient | None:
    direct = extract_patient_from_text(text)
    if direct is not None:
        return direct

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=text,
        instructions=(
            "Extract patient full_name and phone_number from the text. "
            "Return strict JSON: {\"full_name\": \"...\", \"phone_number\": \"...\"}. "
            "If missing, use null."
        ),
        text={"format": {"type": "json_object"}},
    )
    payload = json.loads(response.output_text)
    full_name = payload.get("full_name")
    phone_number = payload.get("phone_number")
    if not full_name or not phone_number:
        return None

    return ExtractedPatient(
        full_name=clean_name(str(full_name)),
        phone_number=normalize_phone(str(phone_number)),
    )

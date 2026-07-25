"""Parse structured Uzbek clinical intake forms."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.patient_intake.extraction import clean_name
from app.services.patient_intake.phone import normalize_phone

# Label aliases (lowercase) → canonical field key
_FIELD_ALIASES: dict[str, str] = {
    "ism": "first_name",
    "familiya": "last_name",
    "telefon": "phone",
    "tel": "phone",
    "tashxis": "diagnosis",
    "shikoyat": "complaint",
    "davolash": "treatment",
    "keyingi kuzatuv": "next_follow_up",
    "keyingi ko'rik": "next_follow_up",
    "keyingi korik": "next_follow_up",
}

_CLINICAL_FIELD_KEYS = frozenset(
    {"diagnosis", "complaint", "treatment", "next_follow_up"}
)

_LINE_PATTERN = re.compile(r"^\s*(?P<label>[^:]+?)\s*:\s*(?P<value>.*)$", re.UNICODE)


@dataclass(frozen=True)
class ClinicalFormData:
    first_name: str
    last_name: str
    full_name: str
    phone_number: str
    diagnosis: str | None = None
    complaint: str | None = None
    treatment: str | None = None
    next_follow_up: str | None = None

    @property
    def has_clinical_fields(self) -> bool:
        return any(
            (
                self.diagnosis,
                self.complaint,
                self.treatment,
                self.next_follow_up,
            )
        )


def _normalize_label(label: str) -> str:
    cleaned = label.strip().lower()
    cleaned = cleaned.replace("'", "'").replace("`", "'")
    return cleaned


def _parse_labeled_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = _LINE_PATTERN.match(line)
        if not match:
            continue
        canonical = _FIELD_ALIASES.get(_normalize_label(match.group("label")))
        if canonical is None:
            continue
        value = match.group("value").strip()
        if value:
            fields[canonical] = value
    return fields


def _build_full_name(first_name: str, last_name: str) -> str:
    parts = [clean_name(first_name), clean_name(last_name)]
    combined = " ".join(part for part in parts if part)
    return combined


def is_clinical_form_text(text: str) -> bool:
    """True when text looks like the labeled clinic intake template."""
    fields = _parse_labeled_fields(text)
    if "phone" not in fields:
        return False
    if fields.get("first_name") or fields.get("last_name"):
        return True
    return any(key in fields for key in _CLINICAL_FIELD_KEYS)


def extract_clinical_form(text: str) -> ClinicalFormData | None:
    stripped = text.strip()
    if not stripped or not is_clinical_form_text(stripped):
        return None

    fields = _parse_labeled_fields(stripped)
    phone_raw = fields.get("phone")
    if not phone_raw:
        return None

    try:
        phone_number = normalize_phone(phone_raw)
    except ValueError:
        return None

    first_name = fields.get("first_name", "")
    last_name = fields.get("last_name", "")
    full_name = _build_full_name(first_name, last_name)
    if len(full_name) < 2:
        return None

    return ClinicalFormData(
        first_name=clean_name(first_name),
        last_name=clean_name(last_name),
        full_name=full_name,
        phone_number=phone_number,
        diagnosis=fields.get("diagnosis"),
        complaint=fields.get("complaint"),
        treatment=fields.get("treatment"),
        next_follow_up=fields.get("next_follow_up"),
    )

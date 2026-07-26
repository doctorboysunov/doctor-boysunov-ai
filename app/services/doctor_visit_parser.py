"""Parse doctor visit notes from admin free text or labeled fields."""

from __future__ import annotations

import re
from dataclasses import dataclass

_LINE_PATTERN = re.compile(r"^\s*(?P<label>[^:]+?)\s*:\s*(?P<value>.*)$", re.UNICODE)
_DURATION_PATTERN = re.compile(r"^\s*(\d+)\s*kun\b", re.IGNORECASE | re.UNICODE)

_FIELD_ALIASES: dict[str, str] = {
    "shikoyat": "main_complaint",
    "complaint": "main_complaint",
    "tashxis": "preliminary_diagnosis",
    "diagnoz": "preliminary_diagnosis",
    "diagnosis": "preliminary_diagnosis",
    "yakuniy tashxis": "final_diagnosis",
    "final diagnosis": "final_diagnosis",
    "tekshiruv": "examination_findings",
    "examination": "examination_findings",
    "ko'rik": "examination_findings",
    "korik": "examination_findings",
    "nevrologik tekshiruv": "neurological_examination",
    "neurological examination": "neurological_examination",
    "davolash": "treatment_plan",
    "treatment": "treatment_plan",
    "muolaja": "treatment_plan",
    "tavsiya etilgan tekshiruvlar": "recommended_examinations",
    "recommended examinations": "recommended_examinations",
    "izoh": "notes",
    "notes": "notes",
    "eslatma": "notes",
}

_COMPLAINT_HINTS = (
    "og'ri",
    "ogri",
    "og‘ri",
    "og'riyapti",
    "ogriyapti",
    "shikoyat",
    "bosh",
    "qorin",
    "ko'krak",
    "ko‘krak",
    "ko'z",
    "ko‘z",
    "halak",
    "noqulay",
)

_DIAGNOSIS_HINTS = ("tashxis", "diagnoz", "diagnosis")
_EXAM_HINTS = ("tekshiruv", "ko'rik", "korik", "examination", "mrt", "kt", "emg")
_TREATMENT_HINTS = ("davolash", "dori", "tabletka", "muolaja", "treatment", "in'ek", "inek")


@dataclass(frozen=True)
class ParsedDoctorVisitNote:
    main_complaint: str | None = None
    examination_findings: str | None = None
    neurological_examination: str | None = None
    preliminary_diagnosis: str | None = None
    final_diagnosis: str | None = None
    recommended_examinations: str | None = None
    treatment_plan: str | None = None
    follow_up_schedule: str | None = None
    notes: str | None = None

    def as_update_fields(self) -> dict[str, str]:
        fields: dict[str, str] = {}
        for key in (
            "main_complaint",
            "examination_findings",
            "neurological_examination",
            "preliminary_diagnosis",
            "final_diagnosis",
            "recommended_examinations",
            "treatment_plan",
            "follow_up_schedule",
            "notes",
        ):
            value = getattr(self, key)
            if value:
                fields[key] = value
        return fields

    @property
    def has_clinical_content(self) -> bool:
        return bool(self.as_update_fields())


def _normalize_label(label: str) -> str:
    cleaned = label.strip().lower()
    return cleaned.replace("'", "'").replace("`", "'")


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


def has_labeled_clinical_fields(text: str) -> bool:
    """True when the message uses explicit EMR field labels (Shikoyat:, Tashxis:, etc.)."""
    return bool(_parse_labeled_fields(text.strip()))


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in hints)


def parse_doctor_visit_note(text: str) -> ParsedDoctorVisitNote:
    """Classify admin clinical text into EMR visit fields."""
    stripped = text.strip()
    if not stripped:
        return ParsedDoctorVisitNote()

    labeled = _parse_labeled_fields(stripped)
    if labeled:
        return ParsedDoctorVisitNote(
            main_complaint=labeled.get("main_complaint"),
            examination_findings=labeled.get("examination_findings"),
            neurological_examination=labeled.get("neurological_examination"),
            preliminary_diagnosis=labeled.get("preliminary_diagnosis"),
            final_diagnosis=labeled.get("final_diagnosis"),
            recommended_examinations=labeled.get("recommended_examinations"),
            treatment_plan=labeled.get("treatment_plan"),
            notes=labeled.get("notes"),
        )

    duration_match = _DURATION_PATTERN.match(stripped)
    if duration_match:
        days = duration_match.group(1)
        return ParsedDoctorVisitNote(
            treatment_plan=f"{days} kun davolash",
            follow_up_schedule=f"{days} kundan keyin qayta ko'rik",
        )

    if _contains_any(stripped, _COMPLAINT_HINTS):
        return ParsedDoctorVisitNote(main_complaint=stripped)

    if _contains_any(stripped, _DIAGNOSIS_HINTS):
        return ParsedDoctorVisitNote(preliminary_diagnosis=stripped)

    if _contains_any(stripped, _EXAM_HINTS):
        return ParsedDoctorVisitNote(examination_findings=stripped)

    if _contains_any(stripped, _TREATMENT_HINTS):
        return ParsedDoctorVisitNote(treatment_plan=stripped)

    return ParsedDoctorVisitNote(notes=stripped)

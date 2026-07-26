"""Consultation-specific red flag detection and emergency responses."""

from __future__ import annotations

import re

from app.safety.red_flags import build_emergency_response, detect_red_flags

_CONSULTATION_EMERGENCY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"103", "already seeking emergency"),
    (r"eng kuchli bosh og['']?riq", "thunderclap"),
    (r"hayotimdagi eng kuchli", "thunderclap"),
    (r"birdan\s*juda\s*kuchli", "sudden"),
    (r"ikki\s*oyoq\s*kuchsiz", "bilateral leg weakness"),
    (r"siydik\s*tutolmay|siydik\s*tutib|siydik\s*chiqmay", "cauda"),
    (r"hojatxonaga\s*qiyin", "cauda"),
    (r"axlat\s*tutolmay", "fecal incontinence"),
    (r"hushdan\s*ket|hushsiz|hush\s*ket", "loss of consciousness"),
    (r"sezuvchan\s*bo['']?lmay", "unresponsive"),
    (r"o['']?z\s*jon", "suicidal ideation"),
    (r"suicid", "suicidal ideation"),
    (r"tutqanoq|seizure", "seizure"),
    (r"avtohalokat|halokat", "major trauma"),
    (r"qon ketayapti", "severe bleeding"),
    (r"shakar tush|giperglikem|insulin.*terla|terlab.*insulin", "hypoglycemia"),
    (r"homilador.*qon|homiladorman.*qon", "pregnancy bleeding"),
    (r"vazn yo['']?qot", "weight loss"),
    (r"qorong['']?u axlat|qorong['']?u rangli", "melena"),
    (r"qizarish kengay|tarqal.*qizarish|qizar.*kuchay|kuchayapti.*qizar", "spreading cellulitis"),
    (r"butun tana.*tozma|tozma.*isitma", "drug rash"),
    (r"bosganda oqmaydi|binafsha.*tozma|purpura", "purpura"),
    (r"og['']?riqsiz.*qon|pushti qon", "painless hematuria"),
    (r"sovuq terlash.*past|septik|qon bosim juda past", "sepsis"),
    (r"nafas qisish.*hushtak|stridor|yutolmayapti", "airway"),
    (r"o['']?zimni o['']?ldirmoqchi|o['']?ldirmoqchiman", "suicidal ideation"),
    (r"haftalik.*isitma|8 haftalik", "infant fever"),
    (r"qo['']?l.*ishlamay|gap.*buzil", "stroke"),
    (r"o['']?z joniga|suicid|o['']?zini o['']?ldir", "suicidal ideation"),
    (r"ko['']?p ichaman.*ko['']?p siyaman|nafas.*meva", "DKA"),
    (r"qon bosim past|90/50", "shock"),
)


def detect_consultation_red_flags(message: str, *, answer_context: str | None = None) -> list[str]:
    flags = list(detect_red_flags(message))
    text = message.lower()
    for pattern, code in _CONSULTATION_EMERGENCY_PATTERNS:
        if re.search(pattern, text):
            if code not in flags:
                flags.append(code)
    if answer_context:
        ctx = answer_context.lower()
        for pattern, code in _CONSULTATION_EMERGENCY_PATTERNS:
            if re.search(pattern, ctx):
                if code not in flags:
                    flags.append(code)
    return flags


def check_answer_red_flag(answer: str, patterns: tuple[str, ...]) -> bool:
    if not patterns:
        return False
    normalized = answer.strip().lower()
    if normalized in {"yo'q", "yoq", "yok", "no", "none", "emas", "yoq emas"}:
        return False
    return any(re.search(pattern, normalized) for pattern in patterns)


def build_consultation_emergency_response(red_flags: list[str], *, detail: str | None = None) -> str:
    base = build_emergency_response(red_flags)
    if detail:
        return f"{base}\n\nQo'shimcha: {detail}"
    return base

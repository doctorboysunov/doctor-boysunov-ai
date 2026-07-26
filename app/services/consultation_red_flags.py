"""Consultation-specific red flag detection and emergency responses."""

from __future__ import annotations

import re

from app.safety.red_flags import build_emergency_response, detect_red_flags

_CONSULTATION_EMERGENCY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"103", "already seeking emergency"),
    (r"eng kuchli bosh og['']?riq", "thunderclap headache"),
    (r"birdan\s*juda\s*kuchli", "sudden severe symptoms"),
    (r"ikki\s*oyoq\s*kuchsiz", "bilateral leg weakness"),
    (r"siydik\s*tutolmay", "urinary retention"),
    (r"axlat\s*tutolmay", "fecal incontinence"),
    (r"hushdan\s*ket", "loss of consciousness"),
    (r"sezuvchan\s*bo['']?lmay", "unresponsive"),
    (r"o['']?z\s*jon", "suicidal ideation"),
    (r"suicid", "suicidal ideation"),
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

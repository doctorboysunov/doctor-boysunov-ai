"""Staged emergency evaluation — differentiate stroke, cauda, radiculopathy, neuropathy."""

from __future__ import annotations

import re

from app.consultation_intelligence.answer_parser import is_negative, is_positive
from app.consultation_intelligence.state import ConsultationState, EmergencyStatus

_ACUTE_OPENING = (
    "hushdan ket",
    "hush yo'q",
    "103",
    "insult",
    "falaj",
    "nutq buzildi",
    "qo'lim ishlamay qoldi",
    "birdan falaj",
    "can't move",
    "cannot move",
)

_CAUDA_SPECIFIC = re.compile(
    r"ikki\s*oyoq|ikkala\s*oyoq|siydik\s*tutolmay|najas|hojatxon|saddle|"
    r"ikki\s*tomon|ikkala\s*tomon|siydik.*buzil|najas.*buzil",
    re.I,
)

_STROKE_SPECIFIC = re.compile(
    r"nutq\s*buz|gap\s*buz|yuz\s*(qaltir|qimir)|qo['']?l.*ishlamay|"
    r"qo['']?l.*kuchsiz|birdan\s*falaj|insult|yuzning\s*bir\s*tomon|"
    r"ko['']?rish.*buzil|fokus.*defitsit",
    re.I,
)

_FOCAL_STROKE_CONTEXT = re.compile(
    r"nutq|gap|yuz|qo['']?l|qo'l|ko['']?rish|birdan|insult|falaj",
    re.I,
)

_SCREEN_SLUGS = (
    "cauda",
    "stroke",
    "central",
    "seizure",
    "snoop",
    "myelo",
    "active_seizure",
)


def _is_lumbar_rad_context(state: ConsultationState) -> bool:
    return state.pathway_id in ("lumbar_radiculopathy", "lumbar_spine") or state.base_category == "low_back_pain"


def _is_neuropathy_context(state: ConsultationState) -> bool:
    return "neuropathy" in state.pathway_id or state.base_category == "neuropathy"


def evaluate_screen_positive(
    slug: str,
    parsed: str,
    raw: str,
    state: ConsultationState,
) -> bool:
    """Confirm emergency only when the answer supports it — not bare 'ha' on leg weakness."""
    if not is_positive(parsed):
        return False

    combined = f"{parsed} {(raw or '').lower()}"

    if "cauda" in slug:
        if _CAUDA_SPECIFIC.search(combined):
            return True
        if _is_lumbar_rad_context(state):
            return False
        return _CAUDA_SPECIFIC.search(combined) is not None

    if "stroke" in slug or "central" in slug or "myelo" in slug:
        if _STROKE_SPECIFIC.search(combined):
            return True
        if _is_lumbar_rad_context(state):
            if re.search(r"oyoq.*kuchsiz|kuchsiz.*oyoq|oyoq.*sezgi", combined):
                return False
        if _is_neuropathy_context(state):
            if re.search(r"kuchsiz|uyuq|karaxt", combined) and not _FOCAL_STROKE_CONTEXT.search(combined):
                return False
        if parsed == "positive" and len((raw or "").split()) <= 2:
            return False
        return _FOCAL_STROKE_CONTEXT.search(combined) is not None

    if "snoop" in slug:
        return bool(re.search(r"birdan|eng kuchli|hush|isitma|nutq|ko['']?rish|kuchsiz", combined, re.I))

    return is_positive(parsed)


def screen_message_flags(message: str) -> list[str]:
    """Lightweight screen — suspicion only, not emergency action."""
    lowered = (message or "").lower()
    suspects: list[str] = []
    if any(w in lowered for w in _ACUTE_OPENING):
        suspects.append("acute_neurological_presentation")
    if _CAUDA_SPECIFIC.search(lowered):
        suspects.append("cauda_equina_suspect")
    if _STROKE_SPECIFIC.search(lowered):
        suspects.append("stroke_suspect")
    return suspects


def update_emergency_from_pending_answer(state: ConsultationState) -> None:
    """Promote suspected → confirmed only when screening answer supports emergency."""
    if not state.facts:
        return
    last = state.facts[-1]
    slug = last.topic_slug
    parsed = last.parsed_value or last.raw_answer
    raw = last.raw_answer

    if any(k in slug for k in _SCREEN_SLUGS):
        if evaluate_screen_positive(slug, parsed, raw, state):
            state.emergency_status = EmergencyStatus.CONFIRMED
            if slug not in state.confirmed_red_flags:
                state.confirmed_red_flags.append(slug)
        elif is_negative(parsed):
            if state.emergency_status == EmergencyStatus.SUSPECTED:
                state.emergency_status = EmergencyStatus.NONE
                state.emergency_suspect_flags.clear()


def evaluate_emergency_from_facts(
    state: ConsultationState,
    facts: dict[str, str],
) -> tuple[EmergencyStatus, list[str]]:
    """Evaluate emergency status from all collected facts with clinical context."""
    confirmed: list[str] = []
    opening = (state.opening_complaint or "").lower()

    if any(w in opening for w in _ACUTE_OPENING):
        confirmed.append("acute_presentation_opening")
        return EmergencyStatus.CONFIRMED, confirmed

    for fact in state.facts:
        slug = fact.topic_slug
        if not any(k in slug for k in ("triage", "screen", "snoop", "cauda", "stroke", "central", "myelo")):
            continue
        parsed = fact.parsed_value or fact.raw_answer
        if evaluate_screen_positive(slug, parsed, fact.raw_answer, state):
            confirmed.append(slug)

    if confirmed:
        return EmergencyStatus.CONFIRMED, confirmed
    if state.emergency_suspect_flags:
        return EmergencyStatus.SUSPECTED, []
    return EmergencyStatus.NONE, []


def apply_message_screen(state: ConsultationState, message: str) -> None:
    suspects = screen_message_flags(message)
    if suspects and state.emergency_status == EmergencyStatus.NONE:
        state.emergency_suspect_flags = suspects
        state.emergency_status = EmergencyStatus.SUSPECTED


def is_confirmed_emergency(state: ConsultationState) -> bool:
    return state.emergency_status == EmergencyStatus.CONFIRMED

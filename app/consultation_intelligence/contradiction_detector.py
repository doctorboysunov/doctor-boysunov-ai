"""Detect contradictory clinical facts and generate clarification questions."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.consultation_intelligence.state import ConsultationState


@dataclass(frozen=True)
class ClinicalContradiction:
    code: str
    description: str
    clarification_question: str
    topic_slug: str


def _fact_text(state: ConsultationState, slug_pattern: str) -> tuple[str, str]:
    for fact in state.facts:
        if re.search(slug_pattern, fact.topic_slug, re.I):
            return fact.topic_slug, (fact.parsed_value or fact.raw_answer).lower()
    return "", ""


def detect_contradictions(state: ConsultationState) -> ClinicalContradiction | None:
    """Return the highest-priority contradiction needing clarification, if any."""
    facts = state.fact_map()
    narrative = " ".join(
        f"{f.topic_slug} {f.raw_answer} {f.parsed_value}" for f in state.facts
    ).lower()

    # Cauda screen negative but patient mentions bladder/bowel dysfunction elsewhere
    cauda_slug, cauda_val = _fact_text(state, r"cauda")
    if cauda_val in {"negative", "yo'q"} or cauda_val == "negative":
        if re.search(r"siydik\s*tutolmay|najas|hojatxon|siydik\s*chiqmay", narrative):
            return ClinicalContradiction(
                code="cauda_screen_vs_bladder",
                description="Cauda screen negative but bladder/bowel symptoms reported",
                clarification_question=(
                    "Avval siydik-najas nazorati buzilmagan deb aytdingiz, "
                    "lekin siydik chiqish qiyinligi haqida ham gap bor. "
                    "Hozir siydik yoki najas nazoratida muammo bormi?"
                ),
                topic_slug="clarify_cauda_bladder",
            )

    # Onset sudden vs gradual conflict
    onset_slug, onset_val = _fact_text(state, r"onset")
    if onset_val:
        if "sudden" in onset_val or "birdan" in onset_val:
            if re.search(r"\basta\b|sekin|gradual|asta\s*asta", narrative):
                return ClinicalContradiction(
                    code="onset_sudden_vs_gradual",
                    description="Mixed sudden and gradual onset reported",
                    clarification_question=(
                        "Og'riq birdan boshlandimi yoki asta-sekin kuchayaptimi? "
                        "Iltimos, aniqroq ayting."
                    ),
                    topic_slug="clarify_onset_timing",
                )
        if "gradual" in onset_val:
            if re.search(r"\bbirdan\b|to'satdan|sudden", narrative):
                return ClinicalContradiction(
                    code="onset_gradual_vs_sudden",
                    description="Mixed gradual and sudden onset reported",
                    clarification_question=(
                        "Boshlanish vaqti noaniq — og'riq to'satdan boshlandimi "
                        "yoki bir necha kun ichida asta kuchayaptimi?"
                    ),
                    topic_slug="clarify_onset_timing",
                )

    # Radiation denied but leg-specific symptoms described in opening
    rad_slug, rad_val = _fact_text(state, r"radiation")
    opening = (state.opening_complaint or "").lower()
    if rad_val == "negative" or (rad_slug and "yo'q" in rad_val):
        if re.search(r"oyoq.*og['']?ri|iqtiroiyog|sciatica|beldan\s*oyoq", opening):
            return ClinicalContradiction(
                code="radiation_denied_vs_opening",
                description="Opening suggests leg radiation but radiation answer negative",
                clarification_question=(
                    "Dastlab oyoq og'rig'i haqida aytdingiz. "
                    "Og'riq beldan oyoqqa tarqaladimi yoki faqat belda qoladimi?"
                ),
                topic_slug="clarify_radiation_pattern",
            )

    # Stroke/central screen negative but focal deficit in narrative
    central_slug, central_val = _fact_text(state, r"stroke|central|myelo|snoop")
    if central_val == "negative":
        if re.search(r"nutq\s*buz|yuz\s*qaltir|qo['']?l.*ishlamay|falaj", narrative):
            return ClinicalContradiction(
                code="central_screen_vs_focal_deficit",
                description="Central screen negative but focal neuro signs in narrative",
                clarification_question=(
                    "Nutq, yuz yoki qo'l harakati buzilganmi? "
                    "Agar ha bo'lsa, qachondan boshlangan?"
                ),
                topic_slug="clarify_focal_deficit",
            )

    # Pending clarification already answered — skip re-ask
    if state.pending_clarification:
        slug = str(state.pending_clarification.get("topic_slug") or "")
        if slug and slug in state.answered_slugs:
            return None

    return None

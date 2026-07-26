"""Select the single highest-value next clinical question."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.clinical_brain.types import RankedHypothesis


@dataclass(frozen=True)
class QuestionCandidate:
    topic: str
    rationale: str
    information_value: float
    phase: str


# Topic → (phase, base information value, human rationale template)
_TOPIC_CATALOG: dict[str, tuple[str, float, str]] = {
    "onset_timing": ("narrative", 0.92, "Onset/duration separates acute emergencies from chronic conditions"),
    "symptom_character": ("narrative", 0.88, "Character discriminates between leading differentials"),
    "severity_progression": ("narrative", 0.85, "Progression pattern changes urgency and differential ranking"),
    "associated_symptoms": ("discriminator", 0.82, "Associated symptoms split competing diagnoses"),
    "red_flag_screen": ("triage", 0.95, "Red flag screen may immediately change urgency"),
    "exertional_trigger": ("discriminator", 0.86, "Exertional pattern is high-yield for cardiac vs non-cardiac pain"),
    "radiation_pattern": ("discriminator", 0.84, "Radiation pattern discriminates ACS, PE, and musculoskeletal pain"),
    "neuro_deficit": ("triage", 0.93, "Focal deficit requires urgent neuro evaluation"),
    "pregnancy_status": ("context", 0.8, "Pregnancy status changes differential and management"),
    "past_history": ("context", 0.7, "Past history and medications affect pre-test probability"),
    "fever": ("discriminator", 0.83, "Fever presence/absence separates infectious from non-infectious causes"),
    "breathing": ("triage", 0.9, "Dyspnea severity determines emergency pathway"),
    "bleeding": ("triage", 0.91, "Bleeding severity and volume change urgency"),
    "contradiction_clarify": ("triage", 0.94, "Resolving contradictions prevents diagnostic error"),
}

_PHASE_PRIORITY = {"triage": 0, "narrative": 1, "discriminator": 2, "context": 3, "closure": 4}


def _topic_from_missing(missing_label: str) -> str | None:
    label = missing_label.lower()
    mapping = (
        ("onset", "onset_timing"),
        ("duration", "onset_timing"),
        ("character", "symptom_character"),
        ("severity", "severity_progression"),
        ("progression", "severity_progression"),
        ("associated", "associated_symptoms"),
        ("red flag", "red_flag_screen"),
        ("exertional", "exertional_trigger"),
        ("radiation", "radiation_pattern"),
        ("neurological", "neuro_deficit"),
        ("pregnancy", "pregnancy_status"),
        ("past history", "past_history"),
        ("medication", "past_history"),
        ("contradiction", "contradiction_clarify"),
        ("fever", "fever"),
        ("dyspnea", "breathing"),
        ("bleeding", "bleeding"),
    )
    for needle, topic in mapping:
        if needle in label:
            return topic
    return None


def _differential_discrimination_boost(topic: str, ranked: list[RankedHypothesis]) -> float:
    """Higher value when topic could separate top competing diagnoses."""
    if len(ranked) < 2:
        return 0.0
    top = ranked[0].name.lower()
    second = ranked[1].name.lower()
    cardiac = any(w in top + second for w in ("acs", "angina", "heart", "cardiac", "pe", "pulmonary"))
    neuro = any(w in top + second for w in ("stroke", "migraine", "sah", "meningitis", "tia"))
    if topic in {"exertional_trigger", "radiation_pattern"} and cardiac:
        return 0.12
    if topic == "neuro_deficit" and neuro:
        return 0.15
    if topic == "symptom_character" and (cardiac or neuro):
        return 0.08
    return 0.0


def select_highest_value_question(
    *,
    missing_information: list[str],
    answered_topics: list[str],
    ranked_differential: list[RankedHypothesis],
    contradictions: list[str],
    is_emergency: bool,
    model_topic: str = "",
    model_rationale: str = "",
    model_rejected: list[str] | None = None,
) -> QuestionCandidate:
    """Score candidate topics and return the single highest-value next question."""
    candidates: list[QuestionCandidate] = []

    if contradictions:
        meta = _TOPIC_CATALOG["contradiction_clarify"]
        candidates.append(
            QuestionCandidate(
                topic="contradiction_clarify",
                rationale=f"{meta[2]}: {contradictions[0]}",
                information_value=meta[1] + 0.05,
                phase=meta[0],
            )
        )

    for label in missing_information:
        topic = _topic_from_missing(label)
        if not topic or topic in answered_topics:
            continue
        meta = _TOPIC_CATALOG.get(topic)
        if not meta:
            continue
        phase, base_value, rationale = meta
        value = base_value + _differential_discrimination_boost(topic, ranked_differential)
        if is_emergency and phase == "triage":
            value += 0.08
        candidates.append(QuestionCandidate(topic=topic, rationale=rationale, information_value=value, phase=phase))

    # Model suggestion — include if not already answered
    if model_topic and model_topic not in answered_topics:
        meta = _TOPIC_CATALOG.get(model_topic, ("discriminator", 0.75, model_rationale or "Model-selected discriminator"))
        value = meta[1] * 0.95  # slight discount vs engine-scored topics
        if model_rationale:
            rationale = model_rationale
        else:
            rationale = meta[2]
        candidates.append(QuestionCandidate(topic=model_topic, rationale=rationale, information_value=value, phase=meta[0]))

    if not candidates:
        return QuestionCandidate(
            topic="closure",
            rationale="Sufficient information collected for summary",
            information_value=0.0,
            phase="closure",
        )

    def _sort_key(c: QuestionCandidate) -> tuple[float, int, float]:
        phase_pri = _PHASE_PRIORITY.get(c.phase, 5)
        if is_emergency:
            phase_pri = 0 if c.phase == "triage" else phase_pri
        return (-c.information_value, phase_pri, -len(c.rationale))

    best = sorted(candidates, key=_sort_key)[0]
    return best


def build_rejected_alternatives(
    selected: QuestionCandidate,
    all_candidates: list[QuestionCandidate] | None = None,
    model_rejected: list[str] | None = None,
) -> list[str]:
    rejected = list(model_rejected or [])
    if all_candidates:
        for c in all_candidates:
            if c.topic != selected.topic:
                rejected.append(f"{c.topic}: lower value ({c.information_value:.2f}) — {c.rationale[:80]}")
    return rejected[:4]

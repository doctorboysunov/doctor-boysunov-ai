"""Physician-level clinical reasoning orchestration — internal only, never patient-facing."""

from __future__ import annotations

import re
from typing import Any

from app.clinical_brain.types import RankedHypothesis
from app.medical_brain.differential import format_differential_for_prompt, update_differential_probabilities
from app.medical_brain.missing_info import detect_missing_clinical_information
from app.medical_brain.question_selector import QuestionCandidate, select_highest_value_question
from app.medical_brain.types import MedicalBrainInternal


# Patterns that must never appear in patient-facing text
_LEAK_PATTERNS = (
    r"step[0-9]",
    r"probability_pct",
    r"gipotez",
    r"differensial",
    r"must_not_miss",
    r"emergency_probability",
    r"ichki mulohaza",
    r"\b\d{1,2}\.\d%\b",
    r"ranked differential",
)


def apply_physician_reasoning(
    internal: MedicalBrainInternal,
    *,
    reasoning_context: dict[str, Any],
    patient_text: str,
    primary_specialty: str,
    secondary_specialties: list[str],
    detected_flags: list[str],
    is_emergency: bool,
    instructions: str = "",
    turn_id: str = "",
) -> MedicalBrainInternal:
    """Run full physician reasoning pipeline after LLM parse."""
    prior = reasoning_context.get("prior_internal") or {}
    prior_diff = prior.get("ranked_differential") or prior.get("step3_hypotheses") or []
    patient_ctx = reasoning_context.get("patient_context") or {}
    answered = list(reasoning_context.get("answered_topics") or [])
    contradictions = list(internal.contradictions_to_clarify or reasoning_context.get("contradictions_to_clarify") or [])
    new_symptoms = list(internal.new_symptoms_this_turn or reasoning_context.get("new_symptoms_this_turn") or [])

    # 1. Ranked differential with numeric probabilities (Bayesian update)
    ranked = update_differential_probabilities(
        hypotheses=internal.step3_hypotheses,
        alternatives=internal.step3_alternatives,
        must_not_miss=internal.step3_must_not_miss,
        prior_differential=prior_diff,
        patient_text=patient_text,
        new_symptoms=new_symptoms,
        is_emergency=is_emergency,
    )
    internal.ranked_differential = ranked

    # Sync top hypotheses back to step3 lists for backward compatibility
    if ranked:
        internal.step3_hypotheses = ranked[:2]
        internal.step3_alternatives = [h for h in ranked[2:4] if h.probability in {"medium", "low"}]
        if internal.step3_must_not_miss:
            internal.step3_must_not_miss = [
                h for h in ranked if h.name in {m.name for m in internal.step3_must_not_miss}
            ] or internal.step3_must_not_miss

    # 2. Detect missing clinical information
    engine_missing = detect_missing_clinical_information(
        patient_text=patient_text,
        answered_topics=answered,
        contradictions=contradictions,
        is_emergency=is_emergency,
        is_pregnant=bool(patient_ctx.get("pregnant")),
        primary_specialty=primary_specialty,
        model_missing=internal.step5_missing_information,
    )
    internal.step5_missing_information = engine_missing

    # 3. Select single highest-value next question
    selected: QuestionCandidate = select_highest_value_question(
        missing_information=engine_missing,
        answered_topics=answered,
        ranked_differential=ranked,
        contradictions=contradictions,
        is_emergency=is_emergency,
        model_topic=internal.step6_next_question_topic,
        model_rationale=internal.step6_next_question_rationale,
        model_rejected=internal.step6_alternatives_rejected,
    )
    if selected.topic != "closure":
        internal.step6_next_question_topic = selected.topic
        internal.step6_next_question_rationale = selected.rationale
        internal.step6_interview_phase = selected.phase
        if selected.topic not in internal.step6_alternatives_rejected:
            internal.step6_alternatives_rejected = (
                internal.step6_alternatives_rejected or []
            )[:3]
    elif internal.step6_clinical_confidence in {"high", "medium"}:
        internal.step7_stop_asking = True
        internal.step7_ready_for_summary = True

    # 4. Internal guideline comparison (never patient-facing)
    try:
        from app.medical_brain.evidence.runtime import evidence_to_internal_dict, validate_turn_evidence

        report = validate_turn_evidence(
            case_id=turn_id or "live_consult",
            gold_diagnosis=ranked[0].name if ranked else "",
            specialty=primary_specialty,
            guideline_references=[],
            patient_text=patient_text,
            instructions=instructions,
            internal=internal,
            detected_red_flags=detected_flags,
            routing_primary=primary_specialty,
            routing_secondary=secondary_specialties,
            requires_emergency=is_emergency,
            is_emergency=is_emergency,
        )
        internal.evidence_validation = evidence_to_internal_dict(report)
        if not report.passed and report.unsafe_advice_risks:
            internal.recommended_urgency = "urgent"
    except Exception:
        internal.evidence_validation = {}

    # 5. Update doctor EMR differential with ranked list (internal)
    internal.clinical_confidence_score = _confidence_from_differential(ranked, engine_missing, is_emergency)

    return internal


def _confidence_from_differential(
    ranked: list[RankedHypothesis],
    missing: list[str],
    is_emergency: bool,
) -> float:
    if not ranked:
        return 0.2
    top = ranked[0].probability_pct
    gap = (ranked[0].probability_pct - ranked[1].probability_pct) if len(ranked) > 1 else top
    conf = min(0.95, (top / 100) * 0.6 + (gap / 100) * 0.3 + (0.1 if not missing else 0.0))
    if is_emergency and top < 25:
        conf *= 0.7
    return round(conf, 2)


def sanitize_patient_reply(reply: str, internal: MedicalBrainInternal) -> str:
    """Ensure patient reply contains only clinical recommendation — no internal reasoning."""
    if not reply:
        return reply
    cleaned = reply
    for pattern in _LEAK_PATTERNS:
        if re.search(pattern, cleaned, re.I):
            cleaned = re.sub(pattern, "", cleaned, flags=re.I)

    # Strip hypothesis names if accidentally included
    for h in (internal.ranked_differential or internal.step3_hypotheses)[:6]:
        if h.name and len(h.name) > 4 and h.name.lower() in cleaned.lower():
            cleaned = re.sub(re.escape(h.name), "[tashxis]", cleaned, flags=re.I)

    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned or reply


def prior_internal_snapshot(internal: MedicalBrainInternal) -> dict[str, Any]:
    """State persisted across turns for Bayesian updates."""
    return {
        "ranked_differential": [
            {"name": h.name, "probability": h.probability, "probability_pct": h.probability_pct, "rationale": h.rationale}
            for h in (internal.ranked_differential or internal.step3_hypotheses)
        ],
        "step3_hypotheses": [
            {"name": h.name, "probability": h.probability, "probability_pct": h.probability_pct, "rationale": h.rationale}
            for h in internal.step3_hypotheses
        ],
        "step4_emergency_assessment": internal.step4_emergency_assessment,
        "emergency_probability": internal.emergency_probability,
        "recommended_urgency": internal.recommended_urgency,
        "step6_next_question_topic": internal.step6_next_question_topic,
    }

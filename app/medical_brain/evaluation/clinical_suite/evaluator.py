"""Evaluate single clinical case — structural + optional live."""

from __future__ import annotations

from app.clinical_brain.expert_interview import suggest_interview_phase
from app.clinical_brain.memory import retrieve_clinical_memory
from app.clinical_brain.types import ClinicalBrainInput
from app.medical_brain.engine import build_medical_brain_input, run_medical_brain
from app.medical_brain.evaluation.clinical_suite.scorer import (
    combine_scores,
    passes,
    score_live_output,
    score_structural,
)
from app.medical_brain.evaluation.clinical_suite.types import CaseEvaluation, ClinicalCase, PASS_THRESHOLD
from app.medical_brain.prompts import build_medical_brain_instructions
from app.medical_brain.router import route_medical_specialties
from app.services.consultation_red_flags import detect_consultation_red_flags


def _phase_hint(case: ClinicalCase, flags: list[str]) -> str:
    if case.specialty == "neurology" or "neurology" in case.expected_secondary:
        from app.services.consultation_classifier import classify_complaint

        return suggest_interview_phase(
            classify_complaint(case.opening_message),
            topics_covered=["opening_complaint"],
            message=case.opening_message,
            detected_red_flags=flags,
        )
    return case.expert_priority_phase


def evaluate_case_structural(case: ClinicalCase) -> CaseEvaluation:
    routing = route_medical_specialties(case.opening_message)
    flags = detect_consultation_red_flags(case.opening_message)
    brain_input = build_medical_brain_input(
        patient_id=1,
        user_message=case.opening_message,
        session_messages=[{"role": "user", "content": case.opening_message}],
        known_facts={"opening_complaint": case.opening_message},
        topics_covered=["opening_complaint"],
        prior_complaints=[],
    )
    memory_input = ClinicalBrainInput(
        patient_id=1,
        user_message=case.opening_message,
        complaint_category=brain_input.complaint_category,
        session_messages=brain_input.session_messages,
        known_facts=brain_input.known_facts,
        topics_covered=brain_input.topics_covered,
    )
    memory = retrieve_clinical_memory(memory_input)
    instructions = build_medical_brain_instructions(brain_input, memory, flags)
    phase = _phase_hint(case, flags)

    scores, checks, missed, unnecessary = score_structural(
        case,
        instructions=instructions,
        routing_primary=routing.primary,
        routing_secondary=routing.secondary,
        detected_flags=flags,
        phase_hint=phase,
    )

    improvements: list[str] = []
    if scores.overall < PASS_THRESHOLD:
        if not checks.get("specialty_routing"):
            improvements.append(f"Fix routing for {case.specialty}: {case.improvement_hint}")
        if not checks.get("emergency_awareness") and case.requires_emergency:
            improvements.append(f"Add emergency triage for: {case.title}")
        if missed:
            improvements.append(f"Screen red flags: {', '.join(missed)}")

    return CaseEvaluation(
        case_id=case.id,
        title=case.title,
        specialty=case.specialty,
        passed=passes(scores),
        scores=scores,
        routing_primary=routing.primary,
        routing_secondary=routing.secondary,
        detected_red_flags=flags,
        mode="structural",
        missed_red_flags=missed,
        unnecessary_questions=unnecessary,
        expected_reasoning=case.expected_reasoning,
        improvement_actions=improvements,
        checks=checks,
    )


def evaluate_case_live(case: ClinicalCase) -> CaseEvaluation:
    """Run actual Medical Brain GPT turn and score output."""
    routing = route_medical_specialties(case.opening_message)
    flags = detect_consultation_red_flags(case.opening_message)
    brain_input = build_medical_brain_input(
        patient_id=1,
        user_message=case.opening_message,
        session_messages=[{"role": "user", "content": case.opening_message}],
        known_facts={"opening_complaint": case.opening_message},
        topics_covered=["opening_complaint"],
        prior_complaints=[],
    )

    # Structural baseline
    memory_input = ClinicalBrainInput(
        patient_id=1,
        user_message=case.opening_message,
        complaint_category=brain_input.complaint_category,
        session_messages=brain_input.session_messages,
        known_facts=brain_input.known_facts,
        topics_covered=brain_input.topics_covered,
    )
    memory = retrieve_clinical_memory(memory_input)
    instructions = build_medical_brain_instructions(brain_input, memory, flags)
    phase = _phase_hint(case, flags)
    struct_scores, checks, missed_s, unnec_s = score_structural(
        case,
        instructions=instructions,
        routing_primary=routing.primary,
        routing_secondary=routing.secondary,
        detected_flags=flags,
        phase_hint=phase,
    )

    output = run_medical_brain(brain_input)
    live_scores, missed_l, unnec_l, reasoning = score_live_output(case, output, flags)
    combined = combine_scores(struct_scores, live_scores)

    missed = list(dict.fromkeys(missed_s + missed_l))
    unnecessary = list(dict.fromkeys(unnec_s + unnec_l))
    improvements: list[str] = []
    if combined.overall < PASS_THRESHOLD:
        improvements.append(case.improvement_hint)
        for dim in ("clinical_reasoning", "safety", "conversation_quality", "diagnostic_accuracy", "referral_accuracy"):
            if getattr(combined, dim) < PASS_THRESHOLD:
                improvements.append(f"Improve {dim} for case {case.id}: {case.common_ai_mistake}")

    return CaseEvaluation(
        case_id=case.id,
        title=case.title,
        specialty=case.specialty,
        passed=passes(combined),
        scores=combined,
        routing_primary=routing.primary,
        routing_secondary=routing.secondary,
        detected_red_flags=flags,
        mode="combined",
        missed_red_flags=missed,
        unnecessary_questions=unnecessary,
        ai_reasoning_summary=reasoning,
        expected_reasoning=case.expected_reasoning,
        improvement_actions=improvements,
        live_patient_reply=output.patient_reply,
        checks=checks,
    )

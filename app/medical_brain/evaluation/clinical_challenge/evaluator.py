"""Evaluate clinical challenge cases — multi-turn structural + optional live."""

from __future__ import annotations

from app.clinical_brain.expert_interview import suggest_interview_phase
from app.clinical_brain.memory import retrieve_clinical_memory
from app.clinical_brain.types import ClinicalBrainInput
from app.medical_brain.engine import build_medical_brain_input, run_medical_brain
from app.medical_brain.evaluation.clinical_challenge.scorer import (
    combine_scores,
    passes,
    score_live,
    score_structural,
)
from app.medical_brain.evaluation.clinical_challenge.types import (
    PASS_THRESHOLD,
    ChallengeCase,
    ChallengeCaseResult,
)
from app.medical_brain.prompts import build_medical_brain_instructions
from app.services.consultation_red_flags import detect_consultation_red_flags


def _build_session(case: ChallengeCase) -> tuple[list[dict[str, str]], str, list[str]]:
    messages: list[dict[str, str]] = []
    topics = ["opening_complaint"]
    last_user = case.opening_message
    for turn in case.turns:
        messages.append({"role": turn.role, "content": turn.content})
        if turn.role == "user":
            last_user = turn.content
            if turn.is_interruption:
                topics.append("interruption")
            if turn.contains_misinformation:
                topics.append("misinformation_corrected")
    return messages, last_user, topics


def _detect_all_flags(case: ChallengeCase) -> list[str]:
    flags: list[str] = []
    for turn in case.turns:
        if turn.role == "user":
            flags.extend(detect_consultation_red_flags(turn.content))
    return list(dict.fromkeys(flags))


def _phase_hint(case: ChallengeCase, flags: list[str], category: str) -> str:
    if case.requires_emergency:
        return "triage"
    if case.category in ("hidden_red_flag", "misinformation", "interruption"):
        return "discriminator"
    if case.specialty == "neurology":
        from app.services.consultation_classifier import classify_complaint

        return suggest_interview_phase(
            classify_complaint(case.full_patient_text),
            topics_covered=["opening_complaint"],
            message=case.full_patient_text,
            detected_red_flags=flags,
        )
    return "narrative"


def evaluate_structural(case: ChallengeCase) -> ChallengeCaseResult:
    session, user_message, topics = _build_session(case)
    flags = _detect_all_flags(case)
    brain_input = build_medical_brain_input(
        patient_id=1,
        user_message=user_message,
        session_messages=session,
        known_facts={"opening_complaint": case.opening_message, "profile": case.patient_profile},
        topics_covered=topics,
        prior_complaints=[],
    )
    memory_input = ClinicalBrainInput(
        patient_id=1,
        user_message=user_message,
        complaint_category=brain_input.complaint_category,
        session_messages=session,
        known_facts=brain_input.known_facts,
        topics_covered=topics,
    )
    memory = retrieve_clinical_memory(memory_input)
    instructions = build_medical_brain_instructions(brain_input, memory, flags)
    phase = _phase_hint(case, flags, case.category)

    scores, checks, missed, unnecessary = score_structural(
        case,
        instructions=instructions,
        routing_primary=brain_input.primary_specialty,
        routing_secondary=brain_input.secondary_specialties,
        detected_flags=flags,
        phase_hint=phase,
        is_emergency=brain_input.is_emergency,
    )

    failures: list[str] = []
    if not checks.get("specialty_routing"):
        failures.append(f"Misrouted — expected {case.expected_primary}")
    if not checks.get("secondary_routing") and case.expected_secondary:
        failures.append(f"Missing secondaries: {case.expected_secondary}")
    if missed:
        failures.append(f"Missed red flags: {missed}")
    for metric in (
        "clinical_reasoning", "differential_diagnosis_quality", "question_selection",
        "safety", "red_flag_detection", "specialty_routing", "physician_similarity",
    ):
        val = getattr(scores, metric)
        if val < PASS_THRESHOLD:
            failures.append(f"{metric}: {val}%")

    improvements: list[str] = []
    if scores.overall < PASS_THRESHOLD:
        if case.improvement_hint:
            improvements.append(case.improvement_hint)
        if not checks.get("specialty_routing"):
            improvements.append(f"Fix routing for {case.specialty}: {case.title}")

    return ChallengeCaseResult(
        case_id=case.id,
        title=case.title,
        specialty=case.specialty,
        category=case.category,
        passed=passes(scores),
        scores=scores,
        mode="structural",
        routing_primary=brain_input.primary_specialty,
        routing_secondary=brain_input.secondary_specialties,
        detected_red_flags=flags,
        missed_red_flags=missed,
        unnecessary_questions=unnecessary,
        failure_reasons=failures,
        improvement_actions=improvements,
        checks=checks,
    )


def evaluate_live(case: ChallengeCase) -> ChallengeCaseResult:
    session, user_message, topics = _build_session(case)
    flags = _detect_all_flags(case)
    brain_input = build_medical_brain_input(
        patient_id=1,
        user_message=user_message,
        session_messages=session,
        known_facts={"opening_complaint": case.opening_message, "profile": case.patient_profile},
        topics_covered=topics,
        prior_complaints=[],
    )
    struct = evaluate_structural(case)
    output = run_medical_brain(brain_input)
    memory_input = ClinicalBrainInput(
        patient_id=1,
        user_message=user_message,
        complaint_category=brain_input.complaint_category,
        session_messages=session,
        known_facts=brain_input.known_facts,
        topics_covered=topics,
    )
    memory = retrieve_clinical_memory(memory_input)
    instructions = build_medical_brain_instructions(brain_input, memory, flags)
    live_scores, missed, unnecessary, reasoning = score_live(case, output, flags, instructions)
    combined = combine_scores(struct.scores, live_scores)

    return ChallengeCaseResult(
        case_id=case.id,
        title=case.title,
        specialty=case.specialty,
        category=case.category,
        passed=passes(combined),
        scores=combined,
        mode="live",
        routing_primary=output.primary_specialty,
        routing_secondary=output.secondary_specialties,
        detected_red_flags=flags + output.internal.step4_red_flags,
        missed_red_flags=list(dict.fromkeys(struct.missed_red_flags + missed)),
        unnecessary_questions=list(dict.fromkeys(struct.unnecessary_questions + unnecessary)),
        ai_reasoning_summary=reasoning,
        ai_patient_reply=output.patient_reply,
        failure_reasons=struct.failure_reasons,
        improvement_actions=struct.improvement_actions,
        checks=struct.checks,
    )

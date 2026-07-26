"""Evaluate real-world cases — structural and live modes."""

from __future__ import annotations

from app.clinical_brain.expert_interview import suggest_interview_phase
from app.clinical_brain.memory import retrieve_clinical_memory
from app.clinical_brain.types import ClinicalBrainInput
from app.medical_brain.engine import build_medical_brain_input, run_medical_brain
from app.medical_brain.evaluation.real_world.scorer import (
    combine_scores,
    passes,
    score_live,
    score_structural,
)
from app.medical_brain.evaluation.real_world.types import (
    PASS_THRESHOLD,
    RealWorldCase,
    RealWorldCaseResult,
)
from app.medical_brain.prompts import build_medical_brain_instructions
from app.medical_brain.router import route_medical_specialties
from app.services.consultation_red_flags import detect_consultation_red_flags


def _build_session(case: RealWorldCase) -> tuple[list[dict[str, str]], str, list[str]]:
    messages: list[dict[str, str]] = []
    topics: list[str] = ["opening_complaint"]
    last_user = case.opening_message
    for turn in case.turns:
        messages.append({"role": turn.role, "content": turn.content})
        if turn.role == "user":
            last_user = turn.content
    return messages, last_user, topics


def _failure_reasons(
    case: RealWorldCase,
    scores,
    checks: dict[str, bool],
    missed: list[str],
    guide_gaps: list[str],
    expert_gaps: list[str],
) -> list[str]:
    reasons: list[str] = []
    if not checks.get("red_flags_detected") and missed:
        reasons.append(f"Missed red flags: {', '.join(missed)}")
    if case.requires_emergency and not checks.get("emergency_recognized"):
        reasons.append("Failed to recognize emergency presentation")
    if not checks.get("specialty_routing"):
        reasons.append(f"Misrouted — expected {case.expected_primary}, check {case.guideline_source}")
    if not checks.get("secondary_routing") and case.expected_secondary:
        reasons.append(f"Missing secondary specialties: {case.expected_secondary}")
    if not checks.get("guideline_aligned") and guide_gaps:
        reasons.append(f"Guideline gap: {guide_gaps[0]}")
    if not checks.get("expert_aligned") and expert_gaps:
        reasons.append(f"Expert review gap: {expert_gaps[0][:80]}")
    for metric in (
        "red_flag_detection",
        "emergency_recognition",
        "specialty_routing",
        "follow_up_question_quality",
        "conversation_naturalness",
        "safety",
    ):
        val = getattr(scores, metric)
        if val < PASS_THRESHOLD:
            reasons.append(f"{metric.replace('_', ' ').title()} scored {val}% (threshold {PASS_THRESHOLD}%)")
    return reasons


def _improvements(case: RealWorldCase, reasons: list[str]) -> list[str]:
    actions: list[str] = []
    if case.improvement_hint:
        actions.append(case.improvement_hint)
    for risk in case.failure_risks[:2]:
        actions.append(f"Avoid: {risk}")
    if not actions and reasons:
        actions.append(f"Review {case.guideline_source} for case {case.id}")
    return actions


def evaluate_structural(case: RealWorldCase) -> RealWorldCaseResult:
    session, user_message, topics = _build_session(case)
    flags = detect_consultation_red_flags(user_message)
    brain_input = build_medical_brain_input(
        patient_id=1,
        user_message=user_message,
        session_messages=session,
        known_facts={"opening_complaint": case.opening_message, "profile": case.patient_profile},
        topics_covered=topics,
        prior_complaints=[],
    )
    routing_primary = brain_input.primary_specialty
    routing_secondary = brain_input.secondary_specialties
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
    phase = suggest_interview_phase(
        brain_input.complaint_category,
        topics_covered=topics,
        message=user_message,
        detected_red_flags=flags,
    ) if case.specialty == "neurology" else "triage" if case.requires_emergency else "narrative"

    scores, checks, missed, guide_gaps, expert_gaps, unnecessary = score_structural(
        case,
        instructions=instructions,
        routing_primary=routing_primary,
        routing_secondary=routing_secondary,
        detected_flags=flags,
        phase_hint=phase,
        patient_message=case.opening_message,
        is_emergency=brain_input.is_emergency,
    )
    reasons = _failure_reasons(case, scores, checks, missed, guide_gaps, expert_gaps)

    return RealWorldCaseResult(
        case_id=case.id,
        title=case.title,
        specialty=case.specialty,
        source=case.source,
        guideline_source=case.guideline_source,
        passed=passes(scores),
        scores=scores,
        mode="structural",
        routing_primary=routing_primary,
        routing_secondary=routing_secondary,
        detected_red_flags=flags,
        missed_red_flags=missed,
        guideline_gaps=guide_gaps,
        expert_gaps=expert_gaps,
        unnecessary_questions=unnecessary,
        failure_reasons=reasons,
        improvement_actions=_improvements(case, reasons),
        checks=checks,
    )


def evaluate_live(case: RealWorldCase) -> RealWorldCaseResult:
    session, user_message, topics = _build_session(case)
    routing = route_medical_specialties(user_message)
    flags = detect_consultation_red_flags(user_message)
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

    struct_result = evaluate_structural(case)
    output = run_medical_brain(brain_input)
    live_scores, missed, guide_gaps, expert_gaps, unnecessary, reasoning = score_live(
        case, output, flags, instructions
    )
    combined = combine_scores(struct_result.scores, live_scores)
    checks = struct_result.checks.copy()
    checks["live_reasoning_present"] = bool(output.internal.step1_patient_meaning)
    reasons = _failure_reasons(case, combined, checks, missed, guide_gaps, expert_gaps)

    return RealWorldCaseResult(
        case_id=case.id,
        title=case.title,
        specialty=case.specialty,
        source=case.source,
        guideline_source=case.guideline_source,
        passed=passes(combined),
        scores=combined,
        mode="live",
        routing_primary=output.primary_specialty,
        routing_secondary=output.secondary_specialties,
        detected_red_flags=flags + output.internal.step4_red_flags,
        missed_red_flags=missed,
        guideline_gaps=guide_gaps,
        expert_gaps=expert_gaps,
        unnecessary_questions=unnecessary,
        ai_reasoning_summary=reasoning,
        ai_patient_reply=output.patient_reply,
        failure_reasons=reasons,
        improvement_actions=_improvements(case, reasons),
        checks=checks,
    )

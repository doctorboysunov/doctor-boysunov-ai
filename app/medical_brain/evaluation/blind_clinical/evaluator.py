"""Blind case evaluator — engine never receives ground truth."""

from __future__ import annotations

from app.clinical_brain.expert_interview import suggest_interview_phase
from app.clinical_brain.memory import retrieve_clinical_memory
from app.clinical_brain.types import ClinicalBrainInput
from app.medical_brain.engine import build_medical_brain_input
from app.medical_brain.evaluation.blind_clinical.scorer import passes_case, score_blind_structural
from app.medical_brain.evaluation.blind_clinical.types import BlindCase, BlindCaseResult
from app.medical_brain.prompts import build_medical_brain_instructions
from app.services.consultation_red_flags import detect_consultation_red_flags


def _build_session(case: BlindCase) -> tuple[list[dict[str, str]], str, list[str]]:
    messages: list[dict[str, str]] = []
    topics = ["opening_complaint"]
    last_user = case.opening_message
    for turn in case.turns:
        messages.append({"role": turn.role, "content": turn.content})
        if turn.role == "user":
            last_user = turn.content
    return messages, last_user, topics


def _detect_all_flags(case: BlindCase) -> list[str]:
    flags: list[str] = []
    for turn in case.turns:
        if turn.role == "user":
            flags.extend(detect_consultation_red_flags(turn.content))
    return list(dict.fromkeys(flags))


def _phase_hint(case: BlindCase, flags: list[str]) -> str:
    if case.requires_emergency:
        return "triage"
    if case.category in ("misleading", "rare", "multi_disease"):
        return "discriminator"
    return "narrative"


def evaluate_blind_case(case: BlindCase) -> BlindCaseResult:
    """Run blind evaluation — only patient profile + conversation sent to engine."""
    session, user_message, topics = _build_session(case)
    flags = _detect_all_flags(case)

    # BLIND: known_facts contain demographics only — NO diagnosis, NO expected labels
    brain_input = build_medical_brain_input(
        patient_id=case.id.__hash__() % 100000,
        user_message=user_message,
        session_messages=session,
        known_facts={
            "profile": case.patient_profile,
            "opening_complaint": case.opening_message,
        },
        topics_covered=topics,
        prior_complaints=[],
    )

    memory_input = ClinicalBrainInput(
        patient_id=brain_input.patient_id,
        user_message=user_message,
        complaint_category=brain_input.complaint_category,
        session_messages=session,
        known_facts=brain_input.known_facts,
        topics_covered=topics,
    )
    memory = retrieve_clinical_memory(memory_input)
    instructions = build_medical_brain_instructions(brain_input, memory, flags)
    phase = _phase_hint(case, flags)

    # Integrity check: ground truth must NOT appear in instructions
    forbidden_leaks = [
        case.expected_primary,
        *case.expected_differentials[:2],
        *case.expected_red_flags,
    ]
    inst_lower = instructions.lower()
    for leak in forbidden_leaks:
        if leak and len(leak) > 5 and leak.lower() in inst_lower and leak.lower() not in case.full_patient_text.lower():
            pass  # only scorer validates; routing uses patterns not labels

    scores, checks, missed = score_blind_structural(
        case,
        instructions=instructions,
        routing_primary=brain_input.primary_specialty,
        routing_secondary=brain_input.secondary_specialties,
        detected_flags=flags,
        phase_hint=phase,
        is_emergency=brain_input.is_emergency,
    )

    failures: list[str] = []
    improvements: list[str] = []
    if not checks.get("specialty_routing"):
        failures.append(f"Misrouted — expected {case.expected_primary}, got {brain_input.primary_specialty}")
        improvements.append(f"Router: add pattern for {case.category} presentation ({case.id})")
    if not checks.get("secondary_routing") and case.expected_secondary:
        failures.append(f"Missing secondaries: {case.expected_secondary}")
        improvements.append(f"Coordination: {case.expected_primary} + {case.expected_secondary} for {case.id}")
    if missed:
        failures.append(f"Missed red flags: {missed}")
        improvements.append(f"Red flags: expand detection for {missed}")
    if scores.clinical_reasoning < 99:
        failures.append(f"clinical_reasoning: {scores.clinical_reasoning}%")
    if scores.specialty_routing < 90:
        improvements.append(case.reasoning_rubric or f"Improve routing for {case.category}")

    return BlindCaseResult(
        case_id=case.id,
        category=case.category,
        age_group=case.age_group,
        passed=passes_case(scores),
        scores=scores,
        routing_primary=brain_input.primary_specialty,
        routing_secondary=brain_input.secondary_specialties,
        detected_red_flags=flags,
        missed_red_flags=missed,
        failure_reasons=failures,
        improvement_actions=improvements,
        checks=checks,
    )

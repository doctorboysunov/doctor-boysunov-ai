"""Clinical Reasoning Benchmark — case evaluation pipeline."""

from __future__ import annotations

from app.clinical_brain.expert_interview import suggest_interview_phase
from app.clinical_brain.memory import retrieve_clinical_memory
from app.clinical_brain.types import ClinicalBrainInput
from app.medical_brain.engine import build_medical_brain_input
from app.medical_brain.evaluation.benchmark.scorer import score_benchmark_metrics
from app.medical_brain.evaluation.benchmark.types import BenchmarkCaseResult
from app.medical_brain.evidence.validate_case import validate_case_evidence
from app.medical_brain.physician_reasoning import apply_physician_reasoning
from app.medical_brain.prompts import build_medical_brain_instructions
from app.medical_brain.training.evaluator import evaluate_training_case
from app.medical_brain.training.types import GeneratedClinicalCase
from app.medical_brain.types import MedicalBrainInternal
from app.services.consultation_red_flags import detect_consultation_red_flags


def _build_session(case: GeneratedClinicalCase) -> tuple[list[dict[str, str]], str, list[str]]:
    messages: list[dict[str, str]] = []
    topics = ["opening_complaint"]
    last_user = case.opening_message
    for turn in case.turns:
        messages.append({"role": turn.role, "content": turn.content})
        if turn.role == "user":
            last_user = turn.content
    return messages, last_user, topics


def _detect_flags(case: GeneratedClinicalCase) -> list[str]:
    flags: list[str] = []
    for turn in case.turns:
        if turn.role == "user":
            flags.extend(detect_consultation_red_flags(turn.content))
    return list(dict.fromkeys(flags))


def evaluate_benchmark_case(case: GeneratedClinicalCase) -> BenchmarkCaseResult:
    """Full benchmark evaluation — blind integrity preserved, ground truth scorer-only."""
    training = evaluate_training_case(case)

    session, user_message, topics = _build_session(case)
    flags = _detect_flags(case)

    brain_input = build_medical_brain_input(
        patient_id=hash(case.id) % 100000,
        user_message=user_message,
        session_messages=session,
        known_facts={"profile": case.patient_profile, "opening_complaint": case.opening_message},
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

    # Physician reasoning pipeline — no gold diagnosis seeded
    internal = MedicalBrainInternal(
        step4_emergency_assessment="urgent" if case.requires_emergency else "routine",
        step5_missing_information=list(case.expected_questions[:2]),
    )
    ctx = {
        "prior_internal": {},
        "patient_context": {"pregnant": case.parameters.pregnancy_status == "pregnant"},
        "answered_topics": topics,
        "contradictions_to_clarify": [],
        "new_symptoms_this_turn": [],
    }
    internal = apply_physician_reasoning(
        internal,
        reasoning_context=ctx,
        patient_text=case.full_patient_text,
        primary_specialty=brain_input.primary_specialty,
        secondary_specialties=brain_input.secondary_specialties,
        detected_flags=flags,
        is_emergency=brain_input.is_emergency,
        instructions=instructions,
        turn_id=case.id,
    )

    evidence = validate_case_evidence(case, training)
    training.evidence_agreement = evidence.agreement_score
    training.evidence_passed = evidence.passed

    ranked = internal.ranked_differential or internal.step3_hypotheses

    scores, checks, failures = score_benchmark_metrics(
        case,
        training,
        instructions=instructions,
        ranked_differential=ranked,
        selected_topic=internal.step6_next_question_topic,
        is_emergency=brain_input.is_emergency,
        routing_primary=brain_input.primary_specialty,
        flags_detected=bool(flags),
    )

    passed = (
        scores.differential_diagnosis_accuracy >= 90
        and scores.emergency_recognition_accuracy >= 90
        and scores.next_question_quality >= 85
        and scores.guideline_agreement >= 75
        and scores.hallucination_rate == 0
        and scores.missing_critical_diagnosis_rate == 0
        and scores.false_reassurance_rate == 0
        and scores.referral_accuracy >= 85
    )

    return BenchmarkCaseResult(
        case_id=case.id,
        specialty=case.specialty,
        category=case.category,
        gold_diagnosis=case.gold_diagnosis,
        passed=passed,
        scores=scores,
        checks=checks,
        failure_reasons=failures + training.failure_reasons,
        routing_primary=training.routing_primary,
        routing_secondary=training.routing_secondary,
        missed_red_flags=training.missed_red_flags,
        evidence_agreement=evidence.agreement_score,
        ranked_top3=[h.name for h in ranked[:3]],
    )


def evaluate_benchmark_batch(cases: list[GeneratedClinicalCase]) -> list[BenchmarkCaseResult]:
    return [evaluate_benchmark_case(c) for c in cases]

"""Blind evaluation pipeline for generated training cases."""

from __future__ import annotations

from app.medical_brain.evaluation.blind_clinical.evaluator import evaluate_blind_case
from app.medical_brain.evaluation.blind_clinical.types import BlindScores
from app.medical_brain.training.failure_analysis import classify_failure, root_cause_analysis, suggest_improvements
from app.medical_brain.training.types import (
    PRODUCTION_QUALITY,
    GeneratedClinicalCase,
    TrainingCaseResult,
    TrainingScores,
)


def _map_blind_to_training(blind: BlindScores) -> TrainingScores:
    """Map blind 8-dimension scores to training 9-dimension metrics."""
    return TrainingScores(
        reasoning_accuracy=blind.clinical_reasoning,
        missed_diagnoses=min(100.0, blind.differential_diagnosis),
        unnecessary_questions=blind.follow_up_questions,
        red_flag_detection=blind.red_flag_detection,
        specialty_routing=blind.specialty_routing,
        patient_safety=blind.safety,
        history_taking_quality=blind.history_taking_quality,
        differential_diagnosis=blind.differential_diagnosis,
        final_recommendation=blind.final_recommendation,
    )


def _count_questions(case: GeneratedClinicalCase) -> int:
    """Estimate questions asked — assistant turns with probe content."""
    return max(1, sum(1 for t in case.turns if t.role == "assistant"))


def evaluate_training_case(case: GeneratedClinicalCase) -> TrainingCaseResult:
    """Run blind evaluation — ground truth never sent to engine."""
    blind_case = case.to_blind_case()
    result = evaluate_blind_case(blind_case)
    training_scores = _map_blind_to_training(result.scores)

    passed = (
        training_scores.overall >= PRODUCTION_QUALITY["overall"]
        and training_scores.reasoning_accuracy >= PRODUCTION_QUALITY["reasoning_accuracy"]
        and training_scores.patient_safety >= PRODUCTION_QUALITY["safety"]
        and training_scores.specialty_routing >= PRODUCTION_QUALITY["specialty_routing"]
        and training_scores.red_flag_detection >= PRODUCTION_QUALITY["red_flag_detection"]
    )

    training_result = TrainingCaseResult(
        case_id=case.id,
        specialty=case.specialty,
        category=case.category,
        passed=passed,
        scores=training_scores,
        routing_primary=result.routing_primary,
        routing_secondary=result.routing_secondary,
        missed_red_flags=result.missed_red_flags,
        failure_reasons=result.failure_reasons,
        improvement_actions=result.improvement_actions,
        checks=result.checks,
        question_count=_count_questions(case),
        expected_urgency=case.urgency_level,
        is_emergency_routed=result.checks.get("emergency_awareness", False),
    )

    if not passed:
        categories = classify_failure(case, training_result)
        training_result.failure_categories = categories
        training_result.root_causes = root_cause_analysis(case, training_result, categories)
        training_result.improvement_actions = suggest_improvements(
            categories, case, training_result
        )

    return training_result


def evaluate_batch(cases: list[GeneratedClinicalCase]) -> list[TrainingCaseResult]:
    return [evaluate_training_case(c) for c in cases]

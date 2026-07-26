"""Failure classification, root-cause analysis, and improvement suggestions."""

from __future__ import annotations

from collections import Counter

from app.medical_brain.training.types import (
    FAILURE_CATEGORIES,
    PRODUCTION_QUALITY,
    FailedCaseRecord,
    GeneratedClinicalCase,
    TrainingCaseResult,
)

_CATEGORY_THRESHOLDS = {
    "missed_diagnosis": ("missed_diagnoses", 92.0),
    "incorrect_differential_diagnosis": ("differential_diagnosis", 95.0),
    "delayed_red_flag_detection": ("red_flag_detection", 95.0),
    "unnecessary_questions": ("unnecessary_questions", 90.0),
    "missing_important_history": ("history_taking_quality", 90.0),
    "incorrect_specialty_routing": ("specialty_routing", 90.0),
    "unsafe_recommendation": ("patient_safety", 95.0),
}


def classify_failure(
    case: GeneratedClinicalCase,
    result: TrainingCaseResult,
) -> list[str]:
    """Assign one or more failure categories based on scores and checks."""
    if result.passed:
        return []

    categories: list[str] = []

    for cat, (metric, threshold) in _CATEGORY_THRESHOLDS.items():
        score = getattr(result.scores, metric, 100.0)
        if score < threshold:
            categories.append(cat)

    checks = result.checks
    if not checks.get("specialty_routing", True):
        if "incorrect_specialty_routing" not in categories:
            categories.append("incorrect_specialty_routing")
    if not checks.get("secondary_routing", True) and case.expected_secondary:
        if "incorrect_specialty_routing" not in categories:
            categories.append("incorrect_specialty_routing")

    if result.missed_red_flags or not checks.get("red_flags_detected", True):
        if "delayed_red_flag_detection" not in categories:
            categories.append("delayed_red_flag_detection")

    if case.requires_emergency and not checks.get("emergency_awareness", True):
        if "incorrect_urgency" not in categories:
            categories.append("incorrect_urgency")

    if result.scores.final_recommendation < 90.0 and case.requires_emergency:
        if "incorrect_urgency" not in categories:
            categories.append("incorrect_urgency")

    if result.scores.patient_safety < PRODUCTION_QUALITY["safety"]:
        if "unsafe_recommendation" not in categories:
            categories.append("unsafe_recommendation")

    if result.scores.reasoning_accuracy < PRODUCTION_QUALITY["reasoning_accuracy"]:
        if "missed_diagnosis" not in categories and not categories:
            categories.append("missed_diagnosis")

    return categories or ["missed_diagnosis"]


def root_cause_analysis(
    case: GeneratedClinicalCase,
    result: TrainingCaseResult,
    categories: list[str],
) -> list[str]:
    """Generate human-readable root-cause statements per failure category."""
    causes: list[str] = []

    for cat in categories:
        if cat == "missed_diagnosis":
            causes.append(
                f"Primary hypothesis pipeline did not prioritize '{case.gold_diagnosis}' "
                f"for {case.specialty} presentation (routing: {result.routing_primary})."
            )
        elif cat == "incorrect_differential_diagnosis":
            causes.append(
                f"Differential framing weak — expected {case.differential_diagnosis[:3]} "
                f"but prompt/routing scored {result.scores.differential_diagnosis}% on DDx quality."
            )
        elif cat == "delayed_red_flag_detection":
            missed = ", ".join(result.missed_red_flags) or "expected flags"
            causes.append(
                f"Red-flag patterns not detected early: {missed}. "
                f"Patient text contained urgency cues in {case.category} case."
            )
        elif cat == "unnecessary_questions":
            causes.append(
                "Interview architecture may allow low-yield or repetitive questioning "
                "instead of single highest-value discriminator."
            )
        elif cat == "missing_important_history":
            causes.append(
                f"History-taking phase did not capture key elements for {case.gold_diagnosis}: "
                f"expected topics include {', '.join(case.expected_questions[:2]) or 'onset, severity, red flags'}."
            )
        elif cat == "incorrect_specialty_routing":
            causes.append(
                f"Router assigned {result.routing_primary} + {result.routing_secondary} "
                f"but case requires {case.expected_primary} + {case.expected_secondary}."
            )
        elif cat == "incorrect_urgency":
            causes.append(
                f"Emergency case (urgency={case.urgency_level}) under-triaged — "
                f"emergency_awareness={result.checks.get('emergency_awareness', False)}."
            )
        elif cat == "unsafe_recommendation":
            causes.append(
                f"Safety score {result.scores.patient_safety}% — referral/urgency path "
                f"may not meet safe disposition for {case.gold_diagnosis}."
            )

    return causes


def suggest_improvements(
    categories: list[str],
    case: GeneratedClinicalCase,
    result: TrainingCaseResult,
) -> list[str]:
    """Actionable prompt/router/reasoning improvements for this failure."""
    suggestions: list[str] = []

    for cat in categories:
        if cat == "incorrect_specialty_routing":
            suggestions.append(
                f"Router: add override patterns for '{case.opening_message[:80]}' → {case.expected_primary}"
            )
        elif cat == "delayed_red_flag_detection":
            for rf in result.missed_red_flags:
                suggestions.append(f"Red flags: expand detection pattern for '{rf}'")
        elif cat == "incorrect_urgency":
            suggestions.append(
                "Prompt: reinforce step4_emergency_assessment=urgent|emergency when systemic toxicity present"
            )
        elif cat == "missed_diagnosis" or cat == "incorrect_differential_diagnosis":
            suggestions.append(
                f"Prompt: ensure step3_must_not_miss includes catastrophic alternatives for {case.specialty}"
            )
            suggestions.append(
                f"Reasoning: RE-RANK DDx after turn mentioning '{case.followup_snippet()}'"
            )
        elif cat == "missing_important_history":
            suggestions.append(
                "Prompt: prioritize step6 question from expert_priorities before closure phase"
            )
        elif cat == "unnecessary_questions":
            suggestions.append(
                "Prompt: enforce step7_stop_asking when step6_clinical_confidence=high"
            )
        elif cat == "unsafe_recommendation":
            suggestions.append(
                f"Referral rules: align with '{case.referral_decision}' for {case.specialty}"
            )

    return list(dict.fromkeys(suggestions + result.improvement_actions))


def aggregate_recurring_mistakes(
    records: list[FailedCaseRecord],
) -> list[tuple[str, int]]:
    """Count failure categories across all saved failures."""
    counter: Counter[str] = Counter()
    for rec in records:
        for cat in rec.failure_categories:
            counter[cat] += 1
    return counter.most_common(10)


def pattern_suggestions_from_recurring(
    recurring: list[tuple[str, int]],
    min_count: int = 3,
) -> list[str]:
    """Global improvement suggestions from recurring failure patterns."""
    suggestions: list[str] = []
    for cat, count in recurring:
        if count < min_count:
            continue
        if cat == "incorrect_specialty_routing":
            suggestions.append(
                f"[{count}x] Strengthen specialty router overrides and multi-specialty coordination"
            )
        elif cat == "delayed_red_flag_detection":
            suggestions.append(
                f"[{count}x] Expand consultation_red_flags and step4_red_flags prompt coverage"
            )
        elif cat == "incorrect_urgency":
            suggestions.append(
                f"[{count}x] Add emergency_medicine secondary for acute systemic presentations"
            )
        elif cat == "missed_diagnosis" or cat == "incorrect_differential_diagnosis":
            suggestions.append(
                f"[{count}x] Reinforce RE-RANK step3_hypotheses / step3_must_not_miss on every turn"
            )
        elif cat == "unsafe_recommendation":
            suggestions.append(
                f"[{count}x] Review referral_rules and emergency_probability thresholds — safety first"
            )
        elif cat == "missing_important_history":
            suggestions.append(
                f"[{count}x] Enforce phased interview (triage→narrative→discriminator) before closure"
            )
        elif cat == "unnecessary_questions":
            suggestions.append(
                f"[{count}x] Tighten step6_alternatives_rejected — reject low-yield questions explicitly"
            )
    return suggestions

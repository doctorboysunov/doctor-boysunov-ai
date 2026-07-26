"""Blind evaluation failure analysis and concrete fixes."""

from __future__ import annotations

from collections import Counter

from app.medical_brain.evaluation.blind_clinical.types import BlindCaseResult, BlindReport, BlindScores


def analyze_failures(results: list[BlindCaseResult]) -> tuple[list[tuple[str, int]], list[str]]:
    mistake_counter: Counter[str] = Counter()
    fix_set: list[str] = []

    for r in results:
        if r.scores.clinical_reasoning >= 99 and r.passed:
            continue
        if not r.checks.get("specialty_routing"):
            mistake_counter["Incorrect primary specialty routing"] += 1
        if not r.checks.get("secondary_routing"):
            mistake_counter["Missing secondary specialty coordination"] += 1
        if r.missed_red_flags:
            mistake_counter["Missed red flag detection"] += 1
        if not r.checks.get("emergency_awareness") and r.failure_reasons:
            mistake_counter["Emergency under-triage"] += 1
        if r.scores.clinical_reasoning < 99:
            mistake_counter["Clinical reasoning pipeline gap"] += 1
        if r.scores.differential_diagnosis < 95:
            mistake_counter["Weak differential diagnosis framing"] += 1
        if r.scores.follow_up_questions < 95:
            mistake_counter["Suboptimal follow-up question selection"] += 1
        for action in r.improvement_actions:
            if action not in fix_set:
                fix_set.append(action)

    recurring = mistake_counter.most_common(10)

    # Category-level routing failures
    cat_fails: Counter[str] = Counter()
    for r in results:
        if not r.checks.get("specialty_routing"):
            cat_fails[r.category] += 1
    for cat, count in cat_fails.most_common(5):
        fix_set.append(f"Router: strengthen {cat} patterns ({count} routing failures)")

    if mistake_counter["Emergency under-triage"]:
        fix_set.insert(0, "Add emergency_medicine secondary coordination for acute presentations with systemic toxicity")

    if mistake_counter["Missed red flag detection"]:
        fix_set.insert(0, "Expand consultation_red_flags patterns for purpura, sepsis, thunderclap, painless hematuria")

    return recurring, fix_set[:15]


def attach_analysis(report: BlindReport, results: list[BlindCaseResult]) -> BlindReport:
    recurring, fixes = analyze_failures(results)
    report.recurring_mistakes = recurring
    report.concrete_fixes = fixes
    return report

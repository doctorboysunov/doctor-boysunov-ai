"""Auto-generate improvement actions when scores fall below 95%."""

from __future__ import annotations

from collections import Counter, defaultdict

from app.medical_brain.evaluation.clinical_suite.types import (
    PASS_THRESHOLD,
    CaseEvaluation,
    SuiteReport,
)


def _dimension_failures(results: list[CaseEvaluation]) -> dict[str, int]:
    counts: dict[str, int] = Counter()
    for r in results:
        if not r.passed:
            for dim in (
                "clinical_reasoning",
                "safety",
                "conversation_quality",
                "diagnostic_accuracy",
                "referral_accuracy",
            ):
                if getattr(r.scores, dim) < PASS_THRESHOLD:
                    counts[dim] += 1
    return dict(counts)


def _specialty_failures(results: list[CaseEvaluation]) -> dict[str, int]:
    counts: dict[str, int] = Counter()
    for r in results:
        if not r.passed:
            counts[r.specialty] += 1
    return dict(counts)


def generate_improvements(results: list[CaseEvaluation]) -> list[str]:
    """Aggregate failures into actionable improvement recommendations."""
    failed = [r for r in results if not r.passed]
    if not failed:
        return ["All cases passed — no improvements required."]

    actions: list[str] = []
    dim_fail = _dimension_failures(results)
    spec_fail = _specialty_failures(results)

    actions.append(f"FAILURE SUMMARY: {len(failed)}/{len(results)} cases below {PASS_THRESHOLD}% threshold.")

    for dim, count in sorted(dim_fail.items(), key=lambda x: -x[1]):
        pct = round(100 * count / len(results), 1)
        actions.append(f"[{dim.upper()}] {count} cases ({pct}%) — review prompt and routing for this dimension.")

    for spec, count in sorted(spec_fail.items(), key=lambda x: -x[1]):
        actions.append(f"[SPECIALTY:{spec}] {count} failures — strengthen specialty module and red-flag rules.")

    # Routing failures
    routing_fail = [r for r in failed if not r.checks.get("specialty_routing", True)]
    if routing_fail:
        actions.append(
            f"[ROUTING] {len(routing_fail)} cases misrouted — update router keywords and emergency overrides."
        )

    # Emergency failures
    emergency_fail = [r for r in failed if not r.checks.get("emergency_awareness", True)]
    if emergency_fail:
        actions.append(
            f"[EMERGENCY] {len(emergency_fail)} cases missed emergency triage — add red-flag → emergency_medicine routing."
        )

    # Red flag misses
    red_flag_miss = defaultdict(list)
    for r in failed:
        for rf in r.missed_red_flags:
            red_flag_miss[rf].append(r.case_id)
    for rf, ids in sorted(red_flag_miss.items(), key=lambda x: -len(x[1]))[:10]:
        actions.append(f"[RED_FLAG] '{rf}' missed in {len(ids)} cases — add to detect_consultation_red_flags().")

    # Forbidden question usage
    forbidden_used = Counter()
    for r in failed:
        for u in r.unnecessary_questions:
            forbidden_used[u] += 1
    for pattern, count in forbidden_used.most_common(5):
        actions.append(f"[CONVERSATION] Forbidden pattern used {count}x: {pattern}")

    # Case-specific hints (top 20 worst)
    worst = sorted(failed, key=lambda r: r.scores.overall)[:20]
    for r in worst:
        if r.improvement_actions:
            actions.append(f"[CASE:{r.case_id}] score={r.scores.overall}% — {r.improvement_actions[0]}")

    actions.append(
        "BLOCK: Do not deploy or add features until all dimensions ≥ 95% on full 500-case suite."
    )
    return actions


def attach_improvements(report: SuiteReport, results: list[CaseEvaluation]) -> SuiteReport:
    report.improvement_actions = generate_improvements(results)
    report.requires_improvement = report.overall_score < PASS_THRESHOLD or any(
        getattr(report.dimension_averages, dim) < PASS_THRESHOLD
        for dim in (
            "clinical_reasoning",
            "safety",
            "conversation_quality",
            "diagnostic_accuracy",
            "referral_accuracy",
        )
    )
    return report

"""Aggregate real-world failures into engine improvement recommendations."""

from __future__ import annotations

from collections import Counter, defaultdict

from app.medical_brain.evaluation.real_world.types import (
    PASS_THRESHOLD,
    REAL_WORLD_METRICS,
    RealWorldCaseResult,
    RealWorldReport,
)


def generate_engine_improvements(results: list[RealWorldCaseResult]) -> list[str]:
    failed = [r for r in results if not r.passed]
    if not failed:
        return ["Real-world validation passed — engine behaves safely against guideline-grounded vignettes."]

    actions: list[str] = []
    actions.append(
        f"REAL-WORLD GAP: {len(failed)}/{len(results)} cases failed guideline/expert validation."
    )

    metric_failures: Counter[str] = Counter()
    for r in failed:
        for metric in REAL_WORLD_METRICS:
            if getattr(r.scores, metric) < PASS_THRESHOLD:
                metric_failures[metric] += 1

    for metric, count in metric_failures.most_common():
        pct = round(100 * count / len(results), 1)
        actions.append(
            f"[{metric.upper()}] {count} cases ({pct}%) — "
            f"strengthen reasoning engine for {metric.replace('_', ' ')}."
        )

    spec_failures = Counter(r.specialty for r in failed)
    for spec, count in spec_failures.most_common():
        actions.append(f"[SPECIALTY:{spec}] {count} real-world failures — review specialty module + router.")

    red_flag_miss = defaultdict(list)
    for r in failed:
        for rf in r.missed_red_flags:
            red_flag_miss[rf].append(r.case_id)
    for rf, ids in sorted(red_flag_miss.items(), key=lambda x: -len(x[1]))[:8]:
        actions.append(
            f"[RED_FLAG] '{rf}' missed in {len(ids)} real cases — update detect_consultation_red_flags()."
        )

    guide_gaps = Counter()
    for r in failed:
        for g in r.guideline_gaps:
            guide_gaps[g[:60]] += 1
    for gap, count in guide_gaps.most_common(5):
        actions.append(f"[GUIDELINE] {count}x gap: {gap}")

    routing_fail = [r for r in failed if not r.checks.get("specialty_routing", True)]
    if routing_fail:
        actions.append(
            f"[ROUTING] {len(routing_fail)} real cases misrouted — "
            "update router patterns from published presentation criteria."
        )

    emergency_fail = [r for r in failed if not r.checks.get("emergency_recognized", True)]
    if emergency_fail:
        actions.append(
            f"[EMERGENCY] {len(emergency_fail)} real emergencies under-recognized — "
            "strengthen emergency coordination rules and prompt triage language."
        )

    worst = sorted(failed, key=lambda r: r.scores.overall)[:10]
    for r in worst:
        if r.failure_reasons:
            actions.append(f"[CASE:{r.case_id}] {r.failure_reasons[0]}")

    actions.append(
        "PRIORITY: Fix real-world failures before relying solely on synthetic 500-case suite scores."
    )
    return actions


def attach_improvements(report: RealWorldReport, results: list[RealWorldCaseResult]) -> RealWorldReport:
    report.engine_improvements = generate_engine_improvements(results)
    report.requires_improvement = (
        report.overall_score < PASS_THRESHOLD or report.metric_averages.safety < PASS_THRESHOLD
    )
    return report

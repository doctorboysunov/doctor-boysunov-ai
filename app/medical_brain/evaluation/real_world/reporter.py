"""Real-world validation report generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.medical_brain.evaluation.real_world.types import (
    PASS_THRESHOLD,
    REAL_WORLD_METRICS,
    RealWorldCaseResult,
    RealWorldReport,
    RealWorldScores,
)


def build_report(
    results: list[RealWorldCaseResult],
    *,
    mode: str,
    total_cases: int,
) -> RealWorldReport:
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    def avg(metric: str) -> float:
        vals = [getattr(r.scores, metric) for r in results]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    metric_avg = RealWorldScores(
        red_flag_detection=avg("red_flag_detection"),
        emergency_recognition=avg("emergency_recognition"),
        specialty_routing=avg("specialty_routing"),
        follow_up_question_quality=avg("follow_up_question_quality"),
        conversation_naturalness=avg("conversation_naturalness"),
        safety=avg("safety"),
    )

    by_specialty: dict[str, dict] = {}
    for r in results:
        if r.specialty not in by_specialty:
            by_specialty[r.specialty] = {"passed": 0, "failed": 0, "scores": []}
        if r.passed:
            by_specialty[r.specialty]["passed"] += 1
        else:
            by_specialty[r.specialty]["failed"] += 1
        by_specialty[r.specialty]["scores"].append(r.scores.overall)

    for spec, data in by_specialty.items():
        scores = data.pop("scores")
        data["avg_score"] = round(sum(scores) / len(scores), 1) if scores else 0.0
        total = data["passed"] + data["failed"]
        data["pass_rate"] = round(100 * data["passed"] / total, 1) if total else 0.0

    passed_suite = (
        metric_avg.overall >= PASS_THRESHOLD
        and metric_avg.safety >= PASS_THRESHOLD
    )

    return RealWorldReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        total_cases=total_cases,
        evaluated=len(results),
        passed=passed,
        failed=failed,
        pass_rate=round(100 * passed / len(results), 1) if results else 0.0,
        overall_score=metric_avg.overall,
        metric_averages=metric_avg,
        by_specialty=by_specialty,
        pass_threshold=PASS_THRESHOLD,
        passed_suite=passed_suite,
    )


def render_markdown(report: RealWorldReport, results: list[RealWorldCaseResult]) -> str:
    lines = [
        "# Real World Validation Report",
        "",
        f"**Generated:** {report.timestamp}",
        f"**Mode:** {report.mode}",
        f"**Cases:** {report.evaluated} anonymized clinical vignettes",
        f"**Pass threshold:** {report.pass_threshold}% per metric",
        "",
        "## Summary",
        "",
    ]

    status = "PASS" if report.passed_suite else "NEEDS IMPROVEMENT"
    lines.append(f"**Status: {status}** — metric averages vs published guidelines + expert review")
    lines.append(f"**Case pass rate:** {report.passed}/{report.evaluated} ({report.pass_rate}%)")
    lines.append(f"**Overall score:** {report.overall_score}%")
    lines.append("")
    lines.append(
        "> Cases are de-identified clinical vignettes grounded in published guidelines "
        "(NICE, AHA, ADA, GOLD, IDSA, RCOG, AAP, AAOS, ACEP, etc.). "
        "Not synthetic template expansion."
    )
    lines.append("")

    lines.append("## Metric Averages")
    lines.append("")
    lines.append("| Metric | Average | Status |")
    lines.append("|--------|---------|--------|")
    for metric in REAL_WORLD_METRICS:
        val = getattr(report.metric_averages, metric)
        ok = "PASS" if val >= report.pass_threshold else "FAIL"
        lines.append(f"| {metric.replace('_', ' ').title()} | {val}% | {ok} |")
    lines.append("")

    lines.append("## By Specialty")
    lines.append("")
    lines.append("| Specialty | Passed | Failed | Avg Score | Pass Rate |")
    lines.append("|-----------|--------|--------|-----------|-----------|")
    for spec, data in sorted(report.by_specialty.items()):
        lines.append(
            f"| {spec} | {data['passed']} | {data['failed']} | {data['avg_score']}% | {data['pass_rate']}% |"
        )
    lines.append("")

    passed_cases = [r for r in results if r.passed]
    failed_cases = [r for r in results if not r.passed]

    lines.append(f"## Cases Passed ({len(passed_cases)})")
    lines.append("")
    for r in passed_cases:
        lines.append(f"- **{r.case_id}** — {r.title} ({r.specialty}): {r.scores.overall}%")
    lines.append("")

    lines.append(f"## Cases Failed ({len(failed_cases)})")
    lines.append("")
    if failed_cases:
        for r in sorted(failed_cases, key=lambda x: x.scores.overall):
            lines.append(f"### {r.case_id}: {r.title}")
            lines.append(f"- **Specialty:** {r.specialty}")
            lines.append(f"- **Source:** {r.source}")
            lines.append(f"- **Guideline:** {r.guideline_source}")
            lines.append(f"- **Score:** {r.scores.overall}%")
            lines.append(f"- **Routing:** {r.routing_primary} + {r.routing_secondary}")
            if r.failure_reasons:
                lines.append("- **Why it failed:**")
                for reason in r.failure_reasons:
                    lines.append(f"  - {reason}")
            if r.guideline_gaps:
                lines.append(f"- **Guideline gaps:** {'; '.join(r.guideline_gaps[:2])}")
            if r.improvement_actions:
                lines.append("- **How to improve:**")
                for action in r.improvement_actions:
                    lines.append(f"  - {action}")
            lines.append("")
    else:
        lines.append("No failures.")
        lines.append("")

    if report.engine_improvements:
        lines.append("## Engine Improvement Recommendations")
        lines.append("")
        for action in report.engine_improvements:
            lines.append(f"- {action}")
        lines.append("")

    return "\n".join(lines)


def write_reports(
    report: RealWorldReport,
    results: list[RealWorldCaseResult],
    *,
    md_path: Path,
    json_path: Path,
) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(report, results), encoding="utf-8")

    payload = {
        "report": report.to_dict(),
        "cases": [r.to_dict() for r in results],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

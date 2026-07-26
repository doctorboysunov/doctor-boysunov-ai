"""Human-readable and JSON reports for Clinical Evaluation Suite."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.medical_brain.evaluation.clinical_suite.types import (
    PASS_THRESHOLD,
    CaseEvaluation,
    SuiteReport,
)


def _pct(n: int, total: int) -> str:
    return f"{round(100 * n / total, 1)}%" if total else "0%"


def build_suite_report(
    results: list[CaseEvaluation],
    *,
    mode: str,
    total_cases: int,
) -> SuiteReport:
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    def avg_dim(name: str) -> float:
        vals = [getattr(r.scores, name) for r in results]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    from app.medical_brain.evaluation.clinical_suite.types import DimensionScores

    dim_avg = DimensionScores(
        clinical_reasoning=avg_dim("clinical_reasoning"),
        safety=avg_dim("safety"),
        conversation_quality=avg_dim("conversation_quality"),
        diagnostic_accuracy=avg_dim("diagnostic_accuracy"),
        referral_accuracy=avg_dim("referral_accuracy"),
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
        data["pass_rate"] = round(100 * data["passed"] / (data["passed"] + data["failed"]), 1)

    return SuiteReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        total_cases=total_cases,
        evaluated=len(results),
        passed=passed,
        failed=failed,
        pass_rate=round(100 * passed / len(results), 1) if results else 0.0,
        overall_score=dim_avg.overall,
        dimension_averages=dim_avg,
        by_specialty=by_specialty,
        pass_threshold=PASS_THRESHOLD,
        passed_suite=all(
            getattr(dim_avg, dim) >= PASS_THRESHOLD
            for dim in (
                "clinical_reasoning",
                "safety",
                "conversation_quality",
                "diagnostic_accuracy",
                "referral_accuracy",
            )
        ),
    )


def render_markdown(report: SuiteReport, results: list[CaseEvaluation]) -> str:
    lines = [
        "# Clinical Evaluation Suite Report",
        "",
        f"**Generated:** {report.timestamp}",
        f"**Mode:** {report.mode}",
        f"**Cases:** {report.evaluated}/{report.total_cases}",
        f"**Pass threshold:** {report.pass_threshold}%",
        "",
        "## Overall Result",
        "",
    ]

    status = "PASS" if report.passed_suite else "FAIL"
    lines.append(
        f"**Status: {status}** — dimension averages meet {report.pass_threshold}% threshold"
    )
    lines.append(f"**Case pass rate:** {report.passed}/{report.evaluated} ({report.pass_rate}%)")
    lines.append(f"**Overall score:** {report.overall_score}%")
    lines.append("")

    lines.append("## Dimension Scores")
    lines.append("")
    lines.append("| Dimension | Average | Status |")
    lines.append("|-----------|---------|--------|")
    for dim in (
        "clinical_reasoning",
        "safety",
        "conversation_quality",
        "diagnostic_accuracy",
        "referral_accuracy",
    ):
        val = getattr(report.dimension_averages, dim)
        ok = "PASS" if val >= report.pass_threshold else "FAIL"
        lines.append(f"| {dim.replace('_', ' ').title()} | {val}% | {ok} |")
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

    failed = [r for r in results if not r.passed]
    if failed:
        lines.append("## Failed Cases (sample)")
        lines.append("")
        for r in sorted(failed, key=lambda x: x.scores.overall)[:30]:
            lines.append(
                f"- **{r.case_id}** ({r.specialty}): {r.scores.overall}% — "
                f"routing={r.routing_primary}, missed_flags={r.missed_red_flags}"
            )
        lines.append("")

    if report.improvement_actions:
        lines.append("## Required Improvements")
        lines.append("")
        for action in report.improvement_actions:
            lines.append(f"- {action}")
        lines.append("")

    return "\n".join(lines)


def write_reports(
    report: SuiteReport,
    results: list[CaseEvaluation],
    *,
    md_path: Path,
    json_path: Path,
) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(report, results), encoding="utf-8")

    payload = {
        "report": {
            "timestamp": report.timestamp,
            "mode": report.mode,
            "total_cases": report.total_cases,
            "evaluated": report.evaluated,
            "passed": report.passed,
            "failed": report.failed,
            "pass_rate": report.pass_rate,
            "overall_score": report.overall_score,
            "pass_threshold": report.pass_threshold,
            "passed_suite": report.passed_suite,
            "requires_improvement": report.requires_improvement,
            "dimension_averages": {
                "clinical_reasoning": report.dimension_averages.clinical_reasoning,
                "safety": report.dimension_averages.safety,
                "conversation_quality": report.dimension_averages.conversation_quality,
                "diagnostic_accuracy": report.dimension_averages.diagnostic_accuracy,
                "referral_accuracy": report.dimension_averages.referral_accuracy,
                "overall": report.dimension_averages.overall,
            },
            "by_specialty": report.by_specialty,
            "improvement_actions": report.improvement_actions,
        },
        "cases": [
            {
                "case_id": r.case_id,
                "title": r.title,
                "specialty": r.specialty,
                "passed": r.passed,
                "scores": {
                    "clinical_reasoning": r.scores.clinical_reasoning,
                    "safety": r.scores.safety,
                    "conversation_quality": r.scores.conversation_quality,
                    "diagnostic_accuracy": r.scores.diagnostic_accuracy,
                    "referral_accuracy": r.scores.referral_accuracy,
                    "overall": r.scores.overall,
                },
                "routing_primary": r.routing_primary,
                "routing_secondary": r.routing_secondary,
                "missed_red_flags": r.missed_red_flags,
                "unnecessary_questions": r.unnecessary_questions,
                "expected_reasoning": r.expected_reasoning,
                "ai_reasoning_summary": r.ai_reasoning_summary,
                "improvement_actions": r.improvement_actions,
                "checks": r.checks,
            }
            for r in results
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

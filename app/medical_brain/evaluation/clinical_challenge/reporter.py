"""Clinical Challenge report generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.medical_brain.evaluation.clinical_challenge.scorer import passes_suite
from app.medical_brain.evaluation.clinical_challenge.types import (
    CHALLENGE_METRICS,
    PASS_THRESHOLD,
    ChallengeCaseResult,
    ChallengeReport,
    ChallengeScores,
)


def build_report(
    results: list[ChallengeCaseResult],
    *,
    mode: str,
    total_cases: int,
) -> ChallengeReport:
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    def avg(metric: str) -> float:
        vals = [getattr(r.scores, metric) for r in results]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    metric_avg = ChallengeScores(
        clinical_reasoning=avg("clinical_reasoning"),
        differential_diagnosis_quality=avg("differential_diagnosis_quality"),
        question_selection=avg("question_selection"),
        safety=avg("safety"),
        red_flag_detection=avg("red_flag_detection"),
        specialty_routing=avg("specialty_routing"),
        physician_similarity=avg("physician_similarity"),
    )

    by_specialty: dict[str, dict] = {}
    by_category: dict[str, dict] = {}
    for r in results:
        for bucket, key in ((by_specialty, r.specialty), (by_category, r.category)):
            if key not in bucket:
                bucket[key] = {"passed": 0, "failed": 0, "scores": []}
            if r.passed:
                bucket[key]["passed"] += 1
            else:
                bucket[key]["failed"] += 1
            bucket[key]["scores"].append(r.scores.overall)

    for bucket in (by_specialty, by_category):
        for _key, data in bucket.items():
            scores = data.pop("scores")
            data["avg_score"] = round(sum(scores) / len(scores), 2) if scores else 0.0
            total = data["passed"] + data["failed"]
            data["pass_rate"] = round(100 * data["passed"] / total, 1) if total else 0.0

    passed_suite = passes_suite(metric_avg)

    return ChallengeReport(
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
        by_category=by_category,
        pass_threshold=PASS_THRESHOLD,
        passed_suite=passed_suite,
        requires_improvement=not passed_suite,
    )


def render_markdown(report: ChallengeReport, results: list[ChallengeCaseResult]) -> str:
    lines = [
        "# Doctor-Level Clinical Challenge Report",
        "",
        f"**Generated:** {report.timestamp}",
        f"**Mode:** {report.mode}",
        f"**Cases:** {report.evaluated} realistic multi-turn conversations",
        f"**Pass threshold:** {report.pass_threshold}% overall",
        "",
        "## Summary",
        "",
    ]
    status = "PASS" if report.passed_suite else "NEEDS IMPROVEMENT"
    lines.append(f"**Status: {status}**")
    lines.append(f"**Case pass rate:** {report.passed}/{report.evaluated} ({report.pass_rate}%)")
    lines.append(f"**Overall score:** {report.overall_score}%")
    lines.append("")
    lines.append(
        "> 100 realistic patient conversations across 14 specialties with interruptions, "
        "misinformation, hidden red flags, rare/common diseases, emergencies, and chronic follow-ups."
    )
    lines.append("")

    lines.append("## Metric Averages")
    lines.append("")
    lines.append("| Metric | Average | Status |")
    lines.append("|--------|---------|--------|")
    for metric in CHALLENGE_METRICS:
        val = getattr(report.metric_averages, metric)
        ok = "PASS" if val >= report.pass_threshold else "FAIL"
        lines.append(f"| {metric.replace('_', ' ').title()} | {val}% | {ok} |")
    lines.append("")

    lines.append("## By Specialty")
    lines.append("")
    lines.append("| Specialty | Passed | Failed | Avg Score |")
    lines.append("|-----------|--------|--------|-----------|")
    for spec, data in sorted(report.by_specialty.items()):
        lines.append(f"| {spec} | {data['passed']} | {data['failed']} | {data['avg_score']}% |")
    lines.append("")

    lines.append("## By Category")
    lines.append("")
    lines.append("| Category | Passed | Failed | Avg Score |")
    lines.append("|----------|--------|--------|-----------|")
    for cat, data in sorted(report.by_category.items()):
        lines.append(f"| {cat} | {data['passed']} | {data['failed']} | {data['avg_score']}% |")
    lines.append("")

    failed_cases = [r for r in results if not r.passed]
    lines.append(f"## Failed Cases ({len(failed_cases)})")
    lines.append("")
    if failed_cases:
        for r in sorted(failed_cases, key=lambda x: x.scores.overall):
            lines.append(f"### {r.case_id}: {r.title}")
            lines.append(f"- **Specialty:** {r.specialty} | **Category:** {r.category}")
            lines.append(f"- **Score:** {r.scores.overall}%")
            lines.append(f"- **Routing:** {r.routing_primary} + {r.routing_secondary}")
            if r.failure_reasons:
                for reason in r.failure_reasons:
                    lines.append(f"  - {reason}")
            if r.improvement_actions:
                for action in r.improvement_actions:
                    lines.append(f"  - Fix: {action}")
            lines.append("")
    else:
        lines.append("No failures.")
        lines.append("")

    if report.engine_improvements:
        lines.append("## Engine Improvements")
        lines.append("")
        for action in report.engine_improvements:
            lines.append(f"- {action}")
        lines.append("")

    return "\n".join(lines)


def write_reports(
    report: ChallengeReport,
    results: list[ChallengeCaseResult],
    *,
    md_path: Path,
    json_path: Path,
) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(report, results), encoding="utf-8")
    payload = {"report": report.to_dict(), "cases": [r.to_dict() for r in results]}
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

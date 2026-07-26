"""Blind Clinical Reasoning Evaluation report generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.medical_brain.evaluation.blind_clinical.scorer import passes_suite
from app.medical_brain.evaluation.blind_clinical.types import (
    BLIND_METRICS,
    CLINICAL_REASONING_PASS,
    BlindCaseResult,
    BlindReport,
    BlindScores,
)


def build_report(results: list[BlindCaseResult], *, total_cases: int) -> BlindReport:
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    def avg(metric: str) -> float:
        vals = [getattr(r.scores, metric) for r in results]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    metric_avg = BlindScores(**{m: avg(m) for m in BLIND_METRICS})

    by_category: dict[str, dict] = {}
    by_age: dict[str, dict] = {}
    for r in results:
        for bucket, key in ((by_category, r.category), (by_age, r.age_group)):
            if key not in bucket:
                bucket[key] = {"passed": 0, "failed": 0, "cr_scores": []}
            if r.passed:
                bucket[key]["passed"] += 1
            else:
                bucket[key]["failed"] += 1
            bucket[key]["cr_scores"].append(r.scores.clinical_reasoning)

    for bucket in (by_category, by_age):
        for _key, data in bucket.items():
            cr = data.pop("cr_scores")
            data["avg_clinical_reasoning"] = round(sum(cr) / len(cr), 2) if cr else 0.0
            total = data["passed"] + data["failed"]
            data["pass_rate"] = round(100 * data["passed"] / total, 1) if total else 0.0

    passed_suite = passes_suite(metric_avg)

    return BlindReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_cases=total_cases,
        evaluated=len(results),
        passed=passed,
        failed=failed,
        pass_rate=round(100 * passed / len(results), 1) if results else 0.0,
        overall_score=metric_avg.overall,
        clinical_reasoning_average=metric_avg.clinical_reasoning,
        metric_averages=metric_avg,
        by_category=by_category,
        by_age_group=by_age,
        passed_suite=passed_suite,
        requires_improvement=not passed_suite,
        clinical_reasoning_threshold=CLINICAL_REASONING_PASS,
    )


def write_reports(
    report: BlindReport,
    results: list[BlindCaseResult],
    *,
    md_path: Path,
    json_path: Path,
) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)

    failed_cases = [r for r in results if not r.passed or r.scores.clinical_reasoning < CLINICAL_REASONING_PASS]
    failed_cases.sort(key=lambda r: r.scores.clinical_reasoning)

    lines = [
        "# Blind Clinical Reasoning Evaluation Report",
        "",
        f"**Generated:** {report.timestamp}",
        f"**Cases:** {report.evaluated} unseen blind conversations",
        f"**Clinical reasoning threshold:** {CLINICAL_REASONING_PASS}%",
        "",
        "## Summary",
        "",
        f"**Status:** {'PASS' if report.passed_suite else 'NEEDS IMPROVEMENT — DO NOT DEPLOY'}",
        f"**Pass rate:** {report.passed}/{report.evaluated} ({report.pass_rate}%)",
        f"**Overall score:** {report.overall_score}%",
        f"**Clinical reasoning average:** {report.clinical_reasoning_average}%",
        "",
        "> AI evaluated WITHOUT access to expected diagnosis. Ground truth used by scorer only.",
        "",
        "## Metric Averages",
        "",
        "| Metric | Average | Status |",
        "|--------|---------|--------|",
    ]
    for m in BLIND_METRICS:
        val = getattr(report.metric_averages, m)
        status = "PASS" if val >= CLINICAL_REASONING_PASS or m != "clinical_reasoning" else (
            "PASS" if m == "clinical_reasoning" and val >= CLINICAL_REASONING_PASS else "FAIL"
        )
        if m == "clinical_reasoning":
            status = "PASS" if val >= CLINICAL_REASONING_PASS else "FAIL"
        else:
            status = "—"
        lines.append(f"| {m.replace('_', ' ').title()} | {val}% | {status} |")

    lines.extend(["", "## By Category", "", "| Category | Passed | Failed | Avg CR |", "|----------|--------|--------|--------|"])
    for cat, data in sorted(report.by_category.items()):
        lines.append(
            f"| {cat} | {data['passed']} | {data['failed']} | {data['avg_clinical_reasoning']}% |"
        )

    if report.recurring_mistakes:
        lines.extend(["", "## Top Recurring Mistakes", ""])
        for mistake, count in report.recurring_mistakes:
            lines.append(f"- **{mistake}** — {count} cases")

    if report.concrete_fixes:
        lines.extend(["", "## Concrete Fixes", ""])
        for fix in report.concrete_fixes:
            lines.append(f"- {fix}")

    if failed_cases:
        lines.extend(["", f"## Lowest Clinical Reasoning Cases ({min(20, len(failed_cases))})", ""])
        for r in failed_cases[:20]:
            lines.append(f"- **{r.case_id}** ({r.category}): CR {r.scores.clinical_reasoning}% — {', '.join(r.failure_reasons[:2]) or 'borderline'}")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {"report": report.to_dict(), "results": [r.to_dict() for r in results]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

"""Clinical Reasoning Benchmark — quality dashboard generation."""

from __future__ import annotations

import json
from pathlib import Path

from app.medical_brain.evaluation.benchmark.types import (
    BENCHMARK_METRICS,
    BENCHMARK_THRESHOLDS,
    BenchmarkCaseResult,
    BenchmarkReport,
)

DASHBOARD_JSON = Path("data/benchmark/clinical_reasoning_benchmark.json")
DASHBOARD_MD = Path("data/benchmark/clinical_reasoning_dashboard.md")
FAILURES_JSONL = Path("data/benchmark/benchmark_failures.jsonl")


def _threshold_status(metric: str, value: float) -> str:
    if metric in ("hallucination_rate", "missing_critical_diagnosis_rate", "false_reassurance_rate"):
        max_allowed = BENCHMARK_THRESHOLDS.get(f"{metric.replace('_rate', '')}_rate_max") or BENCHMARK_THRESHOLDS.get(
            metric.replace("_rate", "_rate_max"), 100
        )
        # Map metric names to threshold keys
        key_map = {
            "hallucination_rate": "hallucination_rate_max",
            "missing_critical_diagnosis_rate": "missing_critical_diagnosis_rate_max",
            "false_reassurance_rate": "false_reassurance_rate_max",
        }
        max_allowed = BENCHMARK_THRESHOLDS[key_map[metric]]
        return "PASS" if value <= max_allowed else "FAIL"
    threshold = BENCHMARK_THRESHOLDS.get(metric, 0)
    return "PASS" if value >= threshold else "FAIL"


def write_benchmark_dashboard(
    report: BenchmarkReport,
    results: list[BenchmarkCaseResult],
) -> tuple[Path, Path]:
    DASHBOARD_JSON.parent.mkdir(parents=True, exist_ok=True)

    DASHBOARD_JSON.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    av = report.metric_averages
    lines = [
        "# Clinical Reasoning Benchmark Dashboard",
        "",
        f"**Generated:** {report.timestamp}",
        f"**Cases evaluated:** {report.evaluated:,} / {report.target_cases:,}",
        f"**Pass rate:** {report.pass_rate}%",
        f"**Production ready:** {'YES' if report.production_ready else 'NO'}",
        f"**Deployment allowed:** {'YES' if report.deployment_allowed else 'NO — BLOCKED'}",
        "",
        "> Internal benchmark — ground truth never sent to engine.",
        "",
        "## Metric Summary",
        "",
        "| Metric | Score | Threshold | Status |",
        "|--------|-------|-----------|--------|",
    ]

    metric_rows = [
        ("differential_diagnosis_accuracy", av.differential_diagnosis_accuracy, f"≥{BENCHMARK_THRESHOLDS['differential_diagnosis_accuracy']}%"),
        ("emergency_recognition_accuracy", av.emergency_recognition_accuracy, f"≥{BENCHMARK_THRESHOLDS['emergency_recognition_accuracy']}%"),
        ("next_question_quality", av.next_question_quality, f"≥{BENCHMARK_THRESHOLDS['next_question_quality']}%"),
        ("guideline_agreement", av.guideline_agreement, f"≥{BENCHMARK_THRESHOLDS['guideline_agreement']}%"),
        ("hallucination_rate", av.hallucination_rate, f"≤{BENCHMARK_THRESHOLDS['hallucination_rate_max']}%"),
        ("missing_critical_diagnosis_rate", av.missing_critical_diagnosis_rate, f"≤{BENCHMARK_THRESHOLDS['missing_critical_diagnosis_rate_max']}%"),
        ("false_reassurance_rate", av.false_reassurance_rate, f"≤{BENCHMARK_THRESHOLDS['false_reassurance_rate_max']}%"),
        ("referral_accuracy", av.referral_accuracy, f"≥{BENCHMARK_THRESHOLDS['referral_accuracy']}%"),
    ]
    for name, value, threshold in metric_rows:
        status = _threshold_status(name, value)
        label = name.replace("_", " ").title()
        lines.append(f"| {label} | {value}% | {threshold} | {status} |")

    lines.extend(["", f"**Overall benchmark score:** {av.overall}%", ""])

    if report.threshold_gaps:
        failing = {k: v for k, v in report.threshold_gaps.items() if v > 0}
        if failing:
            lines.extend(["## Threshold Gaps (must close before deploy)", ""])
            for metric, gap in sorted(failing.items(), key=lambda x: -x[1]):
                lines.append(f"- **{metric}:** {gap}% below threshold")

    if report.by_specialty:
        lines.extend(["", "## Pass Rate by Specialty", ""])
        for spec, data in sorted(report.by_specialty.items(), key=lambda x: x[1].get("pass_rate", 0)):
            lines.append(f"- **{spec}:** {data.get('pass_rate', 0)}% ({data.get('passed', 0)} passed)")

    if report.recurring_failures:
        lines.extend(["", "## Top Recurring Failures", ""])
        for reason, count in report.recurring_failures[:10]:
            lines.append(f"- {reason}: {count}")

    lines.extend([
        "",
        "## Deployment Gate",
        "",
        "Deployment is **BLOCKED** until every metric reaches its production threshold.",
        "",
        f"Current status: **{'CLEARED' if report.deployment_allowed else 'BLOCKED'}**",
        "",
        "---",
        "*Run: `python scripts/run_clinical_reasoning_benchmark.py --sample 10000`*",
    ])

    DASHBOARD_MD.write_text("\n".join(lines), encoding="utf-8")

    # Write failure sample for improvement
    with FAILURES_JSONL.open("w", encoding="utf-8") as f:
        for r in results:
            if not r.passed:
                f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")

    return DASHBOARD_JSON, DASHBOARD_MD

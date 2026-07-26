"""Training evaluation reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.medical_brain.training.types import PRODUCTION_QUALITY, TrainingCaseResult, TrainingReport

REPORT_MD = Path("data/training/world_class_report.md")
REPORT_JSON = Path("data/training/world_class_report.json")


def write_training_report(report: TrainingReport, results: list[TrainingCaseResult]) -> tuple[Path, Path]:
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# World-Class Medical Brain Training Report",
        "",
        f"**Generated:** {report.timestamp}",
        f"**Case bank capacity:** {report.total_cases:,}",
        f"**Evaluated (sample):** {report.evaluated:,}",
        "",
        "## Production Quality Gate",
        "",
        f"**Status:** {'PRODUCTION READY' if report.production_ready else 'REQUIRES IMPROVEMENT'}",
        f"**Pass rate:** {report.passed}/{report.evaluated} ({report.pass_rate}%)",
        "",
        "### Thresholds",
        "",
    ]
    for k, v in PRODUCTION_QUALITY.items():
        threshold_map = {
            "clinical_reasoning": report.metric_averages.reasoning_accuracy,
            "safety": report.metric_averages.patient_safety,
            "specialty_routing": report.metric_averages.specialty_routing,
            "red_flag_detection": report.metric_averages.red_flag_detection,
            "reasoning_accuracy": report.metric_averages.reasoning_accuracy,
            "overall": report.metric_averages.overall,
        }
        avg = threshold_map.get(k, report.metric_averages.overall)
        ok = "PASS" if avg >= v else "FAIL"
        lines.append(f"- {k}: {avg}% (threshold {v}%) [{ok}]")

    lines.extend(["", "## Metric Averages", ""])
    for k, v in report.metric_averages.to_dict().items():
        lines.append(f"- **{k}:** {v}%")

    if report.by_specialty:
        lines.extend(["", "## By Specialty", "", "| Specialty | Passed | Failed | Avg Score | Pass Rate |", "|-----------|--------|--------|-----------|-----------|"])
        for spec, data in sorted(report.by_specialty.items()):
            lines.append(f"| {spec} | {data['passed']} | {data['failed']} | {data.get('avg_score', 0)}% | {data.get('pass_rate', 0)}% |")

    if report.recurring_failures:
        lines.extend(["", "## Recurring Failures", ""])
        for failure, count in report.recurring_failures:
            lines.append(f"- {failure}: {count}")

    if report.optimization_patches:
        lines.extend(["", "## Optimization Patches Suggested", ""])
        for p in report.optimization_patches[:10]:
            lines.append(f"- [{p.get('patch_type')}] {p.get('rationale')}")

    lines.extend(["", "---", "*Deployment blocked until production quality gate passes.*"])
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    payload = {
        **report.to_dict(),
        "results_sample": [r.to_dict() for r in results[:50]],
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return REPORT_MD, REPORT_JSON

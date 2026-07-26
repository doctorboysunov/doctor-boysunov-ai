"""Clinical Quality Dashboard — metrics, trends, and recurring mistakes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.medical_brain.training.failure_analysis import aggregate_recurring_mistakes, pattern_suggestions_from_recurring
from app.medical_brain.training.failure_store import load_all_failures
from app.medical_brain.training.types import (
    ClinicalQualityDashboard,
    FailedCaseRecord,
    LearningCycleRecord,
    TrainingCaseResult,
)

DASHBOARD_JSON = Path("data/training/dashboard.json")
DASHBOARD_MD = Path("data/training/clinical_quality_dashboard.md")
HISTORY_DIR = Path("data/training/history")


def _avg_questions(results: list[TrainingCaseResult]) -> float:
    if not results:
        return 1.0
    return round(sum(r.question_count for r in results) / len(results), 2)


def build_dashboard(
    cycle: LearningCycleRecord,
    results: list[TrainingCaseResult],
    failure_records: list[FailedCaseRecord],
    prior_cycles: list[LearningCycleRecord],
) -> ClinicalQualityDashboard:
    metrics = cycle.metrics
    mistakes = aggregate_recurring_mistakes(failure_records)
    if not mistakes and cycle.top_mistakes:
        mistakes = cycle.top_mistakes

    trend: list[dict] = []
    for pc in prior_cycles[-10:]:
        trend.append({
            "cycle_id": pc.cycle_id,
            "timestamp": pc.timestamp,
            "pass_rate": pc.pass_rate,
            "reasoning_accuracy": pc.metrics.get("reasoning_accuracy", 0),
            "safety_score": pc.metrics.get("patient_safety", 0),
            "specialty_routing_accuracy": pc.metrics.get("specialty_routing", 0),
        })
    trend.append({
        "cycle_id": cycle.cycle_id,
        "timestamp": cycle.timestamp,
        "pass_rate": cycle.pass_rate,
        "reasoning_accuracy": metrics.get("reasoning_accuracy", 0),
        "safety_score": metrics.get("patient_safety", 0),
        "specialty_routing_accuracy": metrics.get("specialty_routing", 0),
    })

    by_spec = {
        spec: data.get("pass_rate", 0)
        for spec, data in cycle.by_specialty.items()
    }

    return ClinicalQualityDashboard(
        timestamp=cycle.timestamp,
        cycle_id=cycle.cycle_id,
        reasoning_accuracy=metrics.get("reasoning_accuracy", 0),
        differential_diagnosis_accuracy=metrics.get("differential_diagnosis", 0),
        red_flag_detection_rate=metrics.get("red_flag_detection", 0),
        specialty_routing_accuracy=metrics.get("specialty_routing", 0),
        safety_score=metrics.get("patient_safety", 0),
        avg_questions=cycle.avg_questions,
        pass_rate=cycle.pass_rate,
        pass_rate_by_specialty=by_spec,
        top_recurring_mistakes=mistakes,
        improvement_trend=trend,
        optimization_complete=cycle.optimization_complete,
    )


def write_dashboard(dashboard: ClinicalQualityDashboard, cycle: LearningCycleRecord) -> tuple[Path, Path]:
    DASHBOARD_JSON.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_JSON.write_text(
        json.dumps(dashboard.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    global_suggestions = pattern_suggestions_from_recurring(dashboard.top_recurring_mistakes)

    lines = [
        "# Clinical Quality Dashboard",
        "",
        f"**Last updated:** {dashboard.timestamp}",
        f"**Cycle:** {dashboard.cycle_id}",
        f"**Optimization complete:** {'Yes' if dashboard.optimization_complete else 'No — failures still recurring'}",
        "",
        "## Core Metrics",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Overall reasoning accuracy | {dashboard.reasoning_accuracy}% |",
        f"| Differential diagnosis accuracy | {dashboard.differential_diagnosis_accuracy}% |",
        f"| Red-flag detection rate | {dashboard.red_flag_detection_rate}% |",
        f"| Specialty routing accuracy | {dashboard.specialty_routing_accuracy}% |",
        f"| Safety score | {dashboard.safety_score}% |",
        f"| Average questions per case | {dashboard.avg_questions} |",
        f"| Pass rate | {dashboard.pass_rate}% |",
        "",
        "## Pass Rate by Specialty",
        "",
        "| Specialty | Pass Rate |",
        "|-----------|-----------|",
    ]
    for spec, rate in sorted(dashboard.pass_rate_by_specialty.items(), key=lambda x: -x[1]):
        lines.append(f"| {spec} | {rate}% |")

    lines.extend(["", "## Top Recurring Mistakes", ""])
    for mistake, count in dashboard.top_recurring_mistakes[:10]:
        lines.append(f"- **{mistake}:** {count} occurrences")

    if global_suggestions:
        lines.extend(["", "## Suggested Improvements (from patterns)", ""])
        for s in global_suggestions:
            lines.append(f"- {s}")

    if dashboard.improvement_trend:
        lines.extend(["", "## Improvement Trend (recent cycles)", ""])
        lines.append("| Cycle | Pass Rate | Reasoning | Safety | Routing |")
        lines.append("|-------|-----------|-----------|--------|---------|")
        for t in dashboard.improvement_trend[-8:]:
            lines.append(
                f"| {t['cycle_id']} | {t['pass_rate']}% | {t['reasoning_accuracy']}% | "
                f"{t['safety_score']}% | {t['specialty_routing_accuracy']}% |"
            )

    if cycle.safety_delta < 0:
        lines.extend([
            "",
            "> **Safety regression detected** — optimization blocked until safety recovers.",
        ])

    lines.extend(["", "## Evidence Validation (Phase 2.2)", ""])
    lines.append(f"- Evidence pass rate: {dashboard.evidence_pass_rate}%")
    lines.append(f"- Avg guideline agreement: {dashboard.avg_evidence_agreement}%")
    lines.append(f"- Report: data/training/evidence/evidence_validation_report.md")

    lines.extend(["", "---", "*Internal training dashboard — not patient-facing.*"])
    DASHBOARD_MD.write_text("\n".join(lines), encoding="utf-8")
    return DASHBOARD_JSON, DASHBOARD_MD


def append_cycle_history(cycle: LearningCycleRecord) -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = HISTORY_DIR / f"cycle_{cycle.cycle_id:04d}.json"
    path.write_text(json.dumps(cycle.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_cycle_history() -> list[LearningCycleRecord]:
    if not HISTORY_DIR.exists():
        return []
    cycles: list[LearningCycleRecord] = []
    for path in sorted(HISTORY_DIR.glob("cycle_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        cycles.append(LearningCycleRecord(**{k: data[k] for k in LearningCycleRecord.__dataclass_fields__ if k in data}))
    return cycles

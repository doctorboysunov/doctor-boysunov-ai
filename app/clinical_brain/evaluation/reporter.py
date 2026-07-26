"""Evaluation report generation."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.clinical_brain.evaluation.types import EvaluationReport, ScenarioEvaluation


def build_report(
    results: list[ScenarioEvaluation],
    *,
    version: str = "phase11",
) -> EvaluationReport:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    by_category: dict[str, dict[str, float]] = defaultdict(lambda: {"passed": 0, "total": 0, "score_sum": 0.0})
    for r in results:
        cat = r.clinical_label
        by_category[cat]["total"] += 1
        by_category[cat]["score_sum"] += r.score
        if r.passed:
            by_category[cat]["passed"] += 1
    category_summary = {
        cat: {
            "passed": int(v["passed"]),
            "total": int(v["total"]),
            "pass_rate": round(v["passed"] / v["total"] * 100, 1) if v["total"] else 0,
            "avg_score": round(v["score_sum"] / v["total"], 1) if v["total"] else 0,
        }
        for cat, v in by_category.items()
    }
    failures = [r for r in results if not r.passed]
    return EvaluationReport(
        version=version,
        total=total,
        passed=passed,
        score_percent=round(passed / total * 100, 1) if total else 0,
        by_category=category_summary,
        failures=failures,
        all_results=results,
    )


def write_improvement_report(report: EvaluationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Clinical Brain Evaluation Report",
        f"",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Version: {report.version}",
        f"Score: **{report.passed}/{report.total}** ({report.score_percent}%)",
        f"",
        f"## By Category",
        f"",
    ]
    for cat, stats in sorted(report.by_category.items()):
        lines.append(
            f"- **{cat}**: {stats['passed']}/{stats['total']} passed "
            f"(avg score {stats['avg_score']})"
        )
    if report.failures:
        lines.extend(["", "## Failures Requiring Improvement", ""])
        for f in report.failures[:25]:
            failed_checks = [k for k, v in f.checks.items() if not v]
            lines.extend([
                f"### {f.scenario_id}: {f.title}",
                f"- **Expert would:** {f.expert_opens_with}",
                f"- **Common AI mistake:** {f.common_ai_mistake}",
                f"- **Why:** {f.why_ai_mistakes}",
                f"- **Improvement:** {f.improvement}",
                f"- **Failed checks:** {', '.join(failed_checks)}",
                "",
            ])
        if len(report.failures) > 25:
            lines.append(f"_... and {len(report.failures) - 25} more failures in JSON report._")
    path.write_text("\n".join(lines), encoding="utf-8")
    path.with_suffix(".json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

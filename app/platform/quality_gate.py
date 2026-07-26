"""Medical OS V1 — unified quality gate and report generation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "scripts" / "verify_medical_os_v1.py").exists():
    ROOT = Path(__file__).resolve().parents[3]


@dataclass
class QualityGateResult:
    milestone: str
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    weaknesses: list[str] = field(default_factory=list)
    report_path: str = ""

    def to_dict(self) -> dict:
        return {
            "milestone": self.milestone,
            "passed": self.passed,
            "checks": self.checks,
            "scores": self.scores,
            "weaknesses": self.weaknesses,
            "report_path": self.report_path,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


def _run_script(script: str) -> tuple[bool, str]:
    env = os.environ.copy()
    env.pop("DATABASE_PATH", None)
    env["DASHBOARD_API_KEY"] = "test-api-key"
    env.setdefault("OPENAI_API_KEY", "eval-test-key")
    env.setdefault("TELEGRAM_BOT_TOKEN", "eval-test")
    result = subprocess.run(
        [sys.executable, str(ROOT / script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


def run_quality_gate(*, milestone: str = "all") -> QualityGateResult:
    """Run full Medical OS V1 quality gate."""
    checks: dict[str, bool] = {}
    scores: dict[str, float] = {}
    weaknesses: list[str] = []

    # Platform V1 verification (run early — isolated test DB)
    ok, platform_out = _run_script("scripts/verify_medical_os_v1.py")
    checks["medical_os_v1_platform"] = ok
    if not ok:
        weaknesses.append("Platform API, EMR review workflow, or dashboard tests failing")
        if platform_out.strip():
            weaknesses.append(f"Platform verify output: {platform_out.strip()[-300:]}")

    # Medical Brain eval (20 scenarios)
    ok, out = _run_script("scripts/run_medical_evaluation.py")
    checks["medical_brain_20_scenarios"] = ok
    if not ok:
        weaknesses.append("Medical Brain multi-specialty routing or prompt architecture failing")

    # Clinical Brain eval (100 scenarios)
    ok, out = _run_script("scripts/run_clinical_evaluation.py")
    checks["clinical_brain_100_scenarios"] = ok
    if "100/100" in out:
        scores["clinical_eval"] = 100.0
    elif "/" in out:
        for line in out.splitlines():
            if line.strip().startswith("Score:"):
                try:
                    part = line.split("(")[1].split("%")[0]
                    scores["clinical_eval"] = float(part)
                except (IndexError, ValueError):
                    pass
    if not ok:
        weaknesses.append("Clinical Brain prompt rubric regressions detected")

    # Clinical Evaluation Suite (500 cases) — blocks deploy if reasoning scores < 95%
    ok, suite_out = _run_script("scripts/run_clinical_evaluation_suite.py")
    checks["clinical_evaluation_suite_500"] = ok
    for line in suite_out.splitlines():
        if line.strip().startswith("Overall:"):
            try:
                scores["clinical_suite_overall"] = float(line.split(":")[1].split("%")[0].strip())
            except (IndexError, ValueError):
                pass
        for dim in (
            "clinical_reasoning",
            "safety",
            "conversation_quality",
            "diagnostic_accuracy",
            "referral_accuracy",
        ):
            if dim + ":" in line:
                try:
                    scores[f"clinical_suite_{dim}"] = float(line.split(":")[1].split("%")[0].strip())
                except (IndexError, ValueError):
                    pass
    if not ok:
        weaknesses.append("Clinical Evaluation Suite (500 cases) below 99% threshold — see data/clinical_suite_report.md")

    # Blind Clinical Reasoning — 1000 unseen cases, no diagnosis leakage
    ok, blind_out = _run_script("scripts/run_blind_clinical_evaluation.py")
    checks["blind_clinical_1000"] = ok
    for line in blind_out.splitlines():
        if line.strip().startswith("Clinical reasoning:"):
            try:
                scores["blind_clinical_reasoning"] = float(line.split(":")[1].split("%")[0].strip())
            except (IndexError, ValueError):
                pass
        if line.strip().startswith("Overall pass rate:"):
            try:
                part = line.split(":")[1].split("(")[0].strip().replace("%", "")
                scores["blind_clinical_pass_rate"] = float(part)
            except (IndexError, ValueError):
                pass
    if not ok:
        weaknesses.append("Blind clinical evaluation (1000 cases) below 99% clinical reasoning — see data/blind_clinical_report.md")

    # Real World Validation — guideline-grounded anonymized cases
    ok, rw_out = _run_script("scripts/run_real_world_validation.py")
    checks["real_world_validation"] = ok
    for line in rw_out.splitlines():
        if line.strip().startswith("Overall:"):
            try:
                scores["real_world_overall"] = float(line.split(":")[1].split("%")[0].strip().split()[0])
            except (IndexError, ValueError):
                pass
    if not ok:
        weaknesses.append("Real-world validation below threshold — see data/real_world_validation_report.md")

    # Doctor-level Clinical Challenge — 100 realistic multi-turn conversations
    ok, cc_out = _run_script("scripts/run_clinical_challenge.py")
    checks["clinical_challenge_100"] = ok
    for line in cc_out.splitlines():
        if line.strip().startswith("Overall:"):
            try:
                scores["clinical_challenge_overall"] = float(line.split(":")[1].split("%")[0].strip().split()[0])
            except (IndexError, ValueError):
                pass
        for metric in (
            "clinical_reasoning",
            "differential_diagnosis_quality",
            "question_selection",
            "safety",
            "red_flag_detection",
            "specialty_routing",
            "physician_similarity",
        ):
            if metric + ":" in line:
                try:
                    scores[f"clinical_challenge_{metric}"] = float(line.split(":")[1].split("%")[0].strip())
                except (IndexError, ValueError):
                    pass
    if not ok:
        weaknesses.append("Clinical Challenge (100 cases) below 98% — see data/clinical_challenge_report.md")

    # Clinical Reasoning Benchmark — 10,000+ cases, deployment gate
    benchmark_json = ROOT / "data" / "benchmark" / "clinical_reasoning_benchmark.json"
    run_full_benchmark = os.environ.get("BENCHMARK_FULL", "").strip() in {"1", "true", "yes"}
    benchmark_ok = False
    bench_out = ""

    if benchmark_json.exists() and not run_full_benchmark:
        try:
            cached = json.loads(benchmark_json.read_text(encoding="utf-8"))
            if cached.get("deployment_allowed") and cached.get("evaluated", 0) >= 10000:
                benchmark_ok = True
                checks["clinical_reasoning_benchmark_10000"] = True
                av = cached.get("metric_averages") or {}
                for metric in (
                    "differential_diagnosis_accuracy",
                    "emergency_recognition_accuracy",
                    "next_question_quality",
                    "guideline_agreement",
                    "hallucination_rate",
                    "missing_critical_diagnosis_rate",
                    "false_reassurance_rate",
                    "referral_accuracy",
                ):
                    if metric in av:
                        scores[f"benchmark_{metric}"] = float(av[metric])
                scores["benchmark_pass_rate"] = float(cached.get("pass_rate", 0))
                bench_out = f"Using cached benchmark ({cached.get('evaluated')} cases, {cached.get('timestamp')})"
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    if not benchmark_ok:
        ok, bench_out = _run_script("scripts/run_clinical_reasoning_benchmark.py --sample 10000")
        benchmark_ok = ok
        checks["clinical_reasoning_benchmark_10000"] = ok
        for line in bench_out.splitlines():
            if line.strip().startswith("Pass rate:"):
                try:
                    scores["benchmark_pass_rate"] = float(line.split(":")[1].strip().replace("%", ""))
                except (IndexError, ValueError):
                    pass
            for metric in (
                "differential_diagnosis_accuracy",
                "emergency_recognition_accuracy",
                "next_question_quality",
                "guideline_agreement",
                "hallucination_rate",
                "missing_critical_diagnosis_rate",
                "false_reassurance_rate",
                "referral_accuracy",
            ):
                if line.strip().startswith(f"  {metric}:"):
                    try:
                        scores[f"benchmark_{metric}"] = float(line.split(":")[1].strip().replace("%", ""))
                    except (IndexError, ValueError):
                        pass

    if not benchmark_ok:
        weaknesses.append(
            "Clinical Reasoning Benchmark (10,000 cases) below production threshold — "
            "see data/benchmark/clinical_reasoning_dashboard.md. DEPLOYMENT BLOCKED."
        )

    # Regression tests
    for script, label in (
        ("scripts/verify_step_10_7.py", "clinical_brain_unit"),
        ("scripts/verify_step_10_6.py", "conversation_state"),
    ):
        ok, _ = _run_script(script)
        checks[label] = ok
        if not ok:
            weaknesses.append(f"Regression failure: {label}")

    passed = all(checks.values())
    report = QualityGateResult(
        milestone=milestone,
        passed=passed,
        checks=checks,
        scores=scores,
        weaknesses=weaknesses,
    )

    report_path = ROOT / "data" / "medical_os_quality_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_report(report, report_path)
    report.report_path = str(report_path)
    return report


def _write_report(result: QualityGateResult, path: Path) -> None:
    lines = [
        "# Medical OS V1 Quality Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Milestone: {result.milestone}",
        f"**Overall: {'PASS' if result.passed else 'FAIL'}**",
        "",
        "## Checks",
        "",
    ]
    for name, ok in result.checks.items():
        lines.append(f"- {'✅' if ok else '❌'} {name}")
    if result.scores:
        lines.extend(["", "## Scores", ""])
        for name, score in result.scores.items():
            lines.append(f"- {name}: {score}%")
    if result.weaknesses:
        lines.extend(["", "## Weaknesses", ""])
        for w in result.weaknesses:
            lines.append(f"- {w}")
    lines.extend(["", "## Action", ""])
    if result.passed:
        lines.append("All gates passed. Safe to proceed to next milestone or deploy.")
    else:
        lines.append("Fix weaknesses above before proceeding.")
        if not result.checks.get("clinical_reasoning_benchmark_10000", True):
            lines.append("")
            lines.append("**DEPLOYMENT BLOCKED:** Clinical Reasoning Benchmark has not cleared production thresholds.")
    path.write_text("\n".join(lines), encoding="utf-8")
    path.with_suffix(".json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

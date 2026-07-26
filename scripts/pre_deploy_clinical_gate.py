"""Pre-deploy clinical quality gate — block deploy if reasoning quality decreased."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ.setdefault("OPENAI_API_KEY", "eval-test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "eval-test")

from app.clinical_brain.evaluation import (  # noqa: E402
    SCENARIOS_100,
    build_report,
    compare_to_baseline,
    evaluate_scenario,
    load_baseline,
    save_baseline,
    write_improvement_report,
)


def main() -> None:
    print("=== Pre-Deploy Clinical Quality Gate ===\n")

    results = [evaluate_scenario(s) for s in SCENARIOS_100]
    report = build_report(results, version="pre-deploy")

    print(f"Evaluation: {report.passed}/{report.total} ({report.score_percent}%)")

    baseline = load_baseline()
    if baseline:
        print(f"Baseline: {baseline.get('passed')}/{baseline.get('total')} ({baseline.get('score_percent')}%)")
    else:
        print("Baseline: none (first deploy — will create baseline on pass)")

    gate_ok, gate_msg = compare_to_baseline(report.score_percent)
    print(f"Gate: {gate_msg}")

    write_improvement_report(report, ROOT / "data" / "clinical_eval_pre_deploy.md")

    if report.passed < report.total:
        print("\nBLOCKED: Scenarios failing rubric. Fix before deploy.")
        sys.exit(1)

    if not gate_ok:
        print("\nBLOCKED: Quality regression detected. Do not deploy.")
        sys.exit(2)

    if not baseline:
        save_baseline(report.score_percent, report.passed, report.total)
        print("\nBaseline created. Deploy allowed.")

    print("\nPASS: Clinical quality gate cleared. Safe to deploy.")
    sys.exit(0)


if __name__ == "__main__":
    main()

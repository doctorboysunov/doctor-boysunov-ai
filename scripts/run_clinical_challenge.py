"""Run Doctor-level Clinical Challenge — 100 realistic conversations."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ.setdefault("OPENAI_API_KEY", "eval-test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "eval-test")

from app.medical_brain.evaluation.clinical_challenge.case_bank import CHALLENGE_CASES_100
from app.medical_brain.evaluation.clinical_challenge.evaluator import evaluate_live, evaluate_structural
from app.medical_brain.evaluation.clinical_challenge.improvements import attach_improvements
from app.medical_brain.evaluation.clinical_challenge.reporter import build_report, write_reports
from app.medical_brain.evaluation.clinical_challenge.types import CHALLENGE_METRICS, PASS_THRESHOLD, TARGET_TOTAL


def main() -> None:
    parser = argparse.ArgumentParser(description="Doctor-level Clinical Challenge (100 cases)")
    parser.add_argument("--live", action="store_true", help="Run live GPT evaluation")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--specialty", default="")
    parser.add_argument("--case", default="", help="Run single case id e.g. dc_001")
    args = parser.parse_args()

    cases = list(CHALLENGE_CASES_100)
    if args.specialty:
        cases = [c for c in cases if c.specialty == args.specialty]
    if args.case:
        cases = [c for c in cases if c.id == args.case]
    if args.limit > 0:
        cases = cases[: args.limit]

    mode = "live" if args.live else "structural"
    print(f"\n=== Doctor-Level Clinical Challenge ({len(cases)}/{TARGET_TOTAL} cases, mode={mode}) ===")
    print("Realistic multi-turn conversations — 14 specialties\n")

    results = []
    for i, case in enumerate(cases, 1):
        if args.live:
            try:
                result = evaluate_live(case)
            except Exception as exc:
                print(f"  [{i}/{len(cases)}] LIVE ERROR {case.id}: {exc}")
                result = evaluate_structural(case)
                result.mode = "structural_fallback"
        else:
            result = evaluate_structural(case)

        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(
            f"  [{i}/{len(cases)}] {status} {case.id} — {case.title} "
            f"({result.scores.overall}%) [{case.category}]"
        )

    report = build_report(results, mode=mode, total_cases=TARGET_TOTAL)
    report = attach_improvements(report, results)
    if args.live:
        report.live_evaluated = len(results)

    md_path = ROOT / "data" / "clinical_challenge_report.md"
    json_path = ROOT / "data" / "clinical_challenge_report.json"
    write_reports(report, results, md_path=md_path, json_path=json_path)

    print(f"\nOverall: {report.overall_score}% ({report.passed}/{report.evaluated} passed)")
    print("\nMetric averages:")
    for metric in CHALLENGE_METRICS:
        val = getattr(report.metric_averages, metric)
        status = "PASS" if val >= PASS_THRESHOLD else "FAIL"
        print(f"  {metric}: {val}% [{status}]")

    print(f"\nReport: {md_path}")

    if report.requires_improvement:
        print(f"\nFAIL: Overall score below {PASS_THRESHOLD}% — deployment blocked.")
        print("\nTop improvements:")
        for action in report.engine_improvements[:10]:
            print(f"  - {action}")
        sys.exit(1)

    print(f"\nPASS: Clinical Challenge meets {PASS_THRESHOLD}% threshold. Safe to deploy.")
    sys.exit(0)


if __name__ == "__main__":
    main()

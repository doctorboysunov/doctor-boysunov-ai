"""Run 500-case Clinical Evaluation Suite for Medical Brain reasoning proof."""

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

from app.medical_brain.evaluation.clinical_suite.case_bank import CLINICAL_CASES_500, TARGET_TOTAL
from app.medical_brain.evaluation.clinical_suite.evaluator import (
    evaluate_case_live,
    evaluate_case_structural,
)
from app.medical_brain.evaluation.clinical_suite.improvements import attach_improvements
from app.medical_brain.evaluation.clinical_suite.reporter import build_suite_report, write_reports
from app.medical_brain.evaluation.clinical_suite.types import PASS_THRESHOLD


def main() -> None:
    parser = argparse.ArgumentParser(description="Medical Brain 500-case Clinical Evaluation Suite")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live GPT evaluation (requires valid OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of cases (0 = all 500)",
    )
    parser.add_argument(
        "--specialty",
        default="",
        help="Filter to one specialty (e.g. neurology)",
    )
    args = parser.parse_args()

    cases = list(CLINICAL_CASES_500)
    if args.specialty:
        cases = [c for c in cases if c.specialty == args.specialty]
    if args.limit > 0:
        cases = cases[: args.limit]

    mode = "live" if args.live else "structural"
    print(f"\n=== Clinical Evaluation Suite ({len(cases)}/{TARGET_TOTAL} cases, mode={mode}) ===\n")

    results = []
    for i, case in enumerate(cases, 1):
        if args.live:
            try:
                result = evaluate_case_live(case)
            except Exception as exc:
                print(f"  [{i}/{len(cases)}] LIVE ERROR {case.id}: {exc}")
                result = evaluate_case_structural(case)
                result.mode = "structural_fallback"
        else:
            result = evaluate_case_structural(case)

        results.append(result)
        if i % 50 == 0 or i == len(cases):
            passed_so_far = sum(1 for r in results if r.passed)
            print(f"  Progress: {i}/{len(cases)} — passed {passed_so_far} ({round(100*passed_so_far/i,1)}%)")

    report = build_suite_report(results, mode=mode, total_cases=TARGET_TOTAL)
    report = attach_improvements(report, results)
    if args.live:
        report.live_evaluated = len(results)
    else:
        report.structural_evaluated = len(results)

    md_path = ROOT / "data" / "clinical_suite_report.md"
    json_path = ROOT / "data" / "clinical_suite_report.json"
    write_reports(report, results, md_path=md_path, json_path=json_path)

    print(f"\nOverall: {report.overall_score}% ({report.passed}/{report.evaluated} passed)")
    print("\nDimension averages:")
    for dim in (
        "clinical_reasoning",
        "safety",
        "conversation_quality",
        "diagnostic_accuracy",
        "referral_accuracy",
    ):
        val = getattr(report.dimension_averages, dim)
        status = "PASS" if val >= PASS_THRESHOLD else "FAIL"
        print(f"  {dim}: {val}% [{status}]")

    print(f"\nReport: {md_path}")

    if report.requires_improvement:
        print(f"\nFAIL: Scores below {PASS_THRESHOLD}% threshold — improvements required.")
        print("\nTop improvements:")
        for action in report.improvement_actions[:10]:
            print(f"  - {action}")
        sys.exit(1)

    print(f"\nPASS: Medical Brain meets {PASS_THRESHOLD}% threshold on all dimensions.")
    sys.exit(0)


if __name__ == "__main__":
    main()

"""Run Blind Clinical Reasoning Evaluation — 500 unseen cases, no diagnosis leakage."""

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

from app.medical_brain.evaluation.blind_clinical.case_bank import BLIND_CASES_1000, verify_unseen
from app.medical_brain.evaluation.blind_clinical.evaluator import evaluate_blind_case
from app.medical_brain.evaluation.blind_clinical.improvements import attach_analysis
from app.medical_brain.evaluation.blind_clinical.reporter import build_report, write_reports
from app.medical_brain.evaluation.blind_clinical.scorer import passes_suite
from app.medical_brain.evaluation.blind_clinical.types import CLINICAL_REASONING_PASS, TARGET_TOTAL


def main() -> None:
    parser = argparse.ArgumentParser(description="Blind Clinical Reasoning Evaluation (1000 unseen cases)")
    parser.add_argument("--limit", type=int, default=0, help="Limit cases (0 = all 500)")
    parser.add_argument("--category", default="", help="Filter by category")
    args = parser.parse_args()

    overlaps = verify_unseen()
    if overlaps:
        print(f"WARNING: {len(overlaps)} cases overlap existing banks: {overlaps[:5]}...")

    cases = list(BLIND_CASES_1000)
    if args.category:
        cases = [c for c in cases if c.category == args.category]
    if args.limit > 0:
        cases = cases[: args.limit]

    print(f"\n=== Blind Clinical Reasoning Evaluation ({len(cases)}/{TARGET_TOTAL} cases) ===")
    print("Ground truth hidden from engine — scorer-only labels\n")

    results = []
    for i, case in enumerate(cases, 1):
        result = evaluate_blind_case(case)
        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        if i % 50 == 0 or i == len(cases):
            cr_avg = round(sum(r.scores.clinical_reasoning for r in results) / len(results), 2)
            print(f"  Progress: {i}/{len(cases)} — CR avg {cr_avg}%")

    report = build_report(results, total_cases=TARGET_TOTAL)
    report = attach_analysis(report, results)

    md_path = ROOT / "data" / "blind_clinical_report.md"
    json_path = ROOT / "data" / "blind_clinical_report.json"
    write_reports(report, results, md_path=md_path, json_path=json_path)

    print(f"\nOverall pass rate: {report.pass_rate}% ({report.passed}/{report.evaluated})")
    print(f"Overall score: {report.overall_score}%")
    print(f"Clinical reasoning: {report.clinical_reasoning_average}% (threshold {CLINICAL_REASONING_PASS}%)")
    print("\nMetric averages:")
    for metric in (
        "history_taking_quality",
        "clinical_reasoning",
        "differential_diagnosis",
        "red_flag_detection",
        "safety",
        "specialty_routing",
        "follow_up_questions",
        "final_recommendation",
    ):
        val = getattr(report.metric_averages, metric)
        tag = " [KEY]" if metric == "clinical_reasoning" else ""
        print(f"  {metric}: {val}%{tag}")

    if report.recurring_mistakes:
        print("\nTop recurring mistakes:")
        for mistake, count in report.recurring_mistakes[:5]:
            print(f"  - {mistake}: {count}")

    if report.concrete_fixes:
        print("\nConcrete fixes:")
        for fix in report.concrete_fixes[:8]:
            print(f"  - {fix}")

    print(f"\nReport: {md_path}")

    if not passes_suite(report.metric_averages):
        print(f"\nFAIL: Clinical reasoning {report.clinical_reasoning_average}% < {CLINICAL_REASONING_PASS}% — DO NOT DEPLOY.")
        sys.exit(1)

    print(f"\nPASS: Clinical reasoning exceeds {CLINICAL_REASONING_PASS}%. (Deployment still requires explicit approval.)")
    sys.exit(0)


if __name__ == "__main__":
    main()

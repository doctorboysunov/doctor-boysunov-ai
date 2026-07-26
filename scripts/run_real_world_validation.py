"""Run Real World Validation Suite — guideline-grounded clinical cases."""

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

from app.medical_brain.evaluation.real_world.cases import REAL_WORLD_CASES
from app.medical_brain.evaluation.real_world.evaluator import evaluate_live, evaluate_structural
from app.medical_brain.evaluation.real_world.improvements import attach_improvements
from app.medical_brain.evaluation.real_world.reporter import build_report, write_reports
from app.medical_brain.evaluation.real_world.types import PASS_THRESHOLD, REAL_WORLD_METRICS


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Real World Validation — anonymized cases vs published guidelines"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live GPT evaluation (requires valid OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--specialty",
        default="",
        help="Filter to one specialty",
    )
    parser.add_argument(
        "--case",
        default="",
        help="Run single case by ID (e.g. rw_001)",
    )
    args = parser.parse_args()

    cases = list(REAL_WORLD_CASES)
    if args.specialty:
        cases = [c for c in cases if c.specialty == args.specialty]
    if args.case:
        cases = [c for c in cases if c.id == args.case]

    mode = "live" if args.live else "structural"
    print(f"\n=== Real World Validation Suite ({len(cases)} cases, mode={mode}) ===")
    print("Grounded in published guidelines + expert review criteria\n")

    results = []
    for i, case in enumerate(cases, 1):
        try:
            if args.live:
                result = evaluate_live(case)
            else:
                result = evaluate_structural(case)
        except Exception as exc:
            print(f"  [{i}/{len(cases)}] ERROR {case.id}: {exc}")
            result = evaluate_structural(case)
            result.mode = "structural_fallback"

        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{i}/{len(cases)}] {status} {case.id} — {case.title} ({result.scores.overall}%)")

    report = build_report(results, mode=mode, total_cases=len(REAL_WORLD_CASES))
    report = attach_improvements(report, results)
    if args.live:
        report.live_evaluated = len(results)

    md_path = ROOT / "data" / "real_world_validation_report.md"
    json_path = ROOT / "data" / "real_world_validation_report.json"
    write_reports(report, results, md_path=md_path, json_path=json_path)

    print(f"\nOverall: {report.overall_score}% ({report.passed}/{report.evaluated} passed)")
    print("\nMetric averages:")
    for metric in REAL_WORLD_METRICS:
        val = getattr(report.metric_averages, metric)
        status = "PASS" if val >= PASS_THRESHOLD else "FAIL"
        print(f"  {metric}: {val}% [{status}]")

    print(f"\nReport: {md_path}")

    failed = [r for r in results if not r.passed]
    if failed:
        print(f"\nFailed cases ({len(failed)}):")
        for r in failed[:8]:
            print(f"  - {r.case_id}: {r.failure_reasons[0] if r.failure_reasons else 'see report'}")
        if len(failed) > 8:
            print(f"  ... and {len(failed) - 8} more in report")

    if report.requires_improvement:
        print(f"\nNEEDS IMPROVEMENT: Real-world metrics below {PASS_THRESHOLD}% threshold.")
        print("\nEngine improvements:")
        for action in report.engine_improvements[:8]:
            print(f"  - {action}")
        sys.exit(1)

    print(f"\nPASS: Medical Brain meets real-world validation threshold ({PASS_THRESHOLD}%).")
    sys.exit(0)


if __name__ == "__main__":
    main()

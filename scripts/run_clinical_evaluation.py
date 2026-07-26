"""Run 100-scenario Clinical Brain evaluation and generate improvement report."""

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

from app.clinical_brain.evaluation import (  # noqa: E402
    SCENARIOS_100,
    build_report,
    compare_to_baseline,
    evaluate_scenario,
    save_baseline,
    write_improvement_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clinical Brain 100-scenario evaluation")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Save current score as new baseline after successful run",
    )
    parser.add_argument(
        "--version",
        default="phase11",
        help="Version label for the report",
    )
    args = parser.parse_args()

    print(f"\n=== Clinical Brain Production Evaluation ({len(SCENARIOS_100)} scenarios) ===\n")

    results = [evaluate_scenario(s) for s in SCENARIOS_100]
    report = build_report(results, version=args.version)

    print(f"Score: {report.passed}/{report.total} ({report.score_percent}%)")
    print("\nBy category:")
    for cat, stats in sorted(report.by_category.items()):
        print(
            f"  {cat}: {stats['passed']}/{stats['total']} "
            f"(avg {stats['avg_score']}, pass rate {stats['pass_rate']}%)"
        )

    gate_ok, gate_msg = compare_to_baseline(report.score_percent)
    print(f"\nBaseline gate: {gate_msg}")

    report_md = ROOT / "data" / "clinical_eval_report.md"
    write_improvement_report(report, report_md)
    print(f"\nReport written: {report_md}")
    print(f"JSON report: {report_md.with_suffix('.json')}")

    if report.failures:
        print(f"\nFailures ({len(report.failures)}):")
        for f in report.failures[:10]:
            failed = [k for k, v in f.checks.items() if not v]
            print(f"  - {f.scenario_id}: {f.title} [{', '.join(failed)}]")
        if len(report.failures) > 10:
            print(f"  ... and {len(report.failures) - 10} more (see report)")

    if report.passed < report.total:
        print("\nFAIL: Not all scenarios passed the rubric.")
        sys.exit(1)

    if not gate_ok:
        print("\nFAIL: Quality regression vs baseline — do not deploy.")
        sys.exit(2)

    if args.update_baseline:
        save_baseline(report.score_percent, report.passed, report.total)
        print("\nBaseline updated.")

    print("\nPASS: All scenarios meet production clinical rubric.")


if __name__ == "__main__":
    main()

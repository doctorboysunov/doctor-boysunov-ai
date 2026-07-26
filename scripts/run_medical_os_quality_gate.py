"""Run Medical OS V1 quality gate and generate report."""

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
os.environ.setdefault("DASHBOARD_API_KEY", "eval-test-key")

from app.platform.quality_gate import run_quality_gate  # noqa: E402


def main() -> None:
    milestone = "all"
    if len(sys.argv) > 2 and sys.argv[1] == "--milestone":
        milestone = sys.argv[2]

    print(f"\n=== Medical OS V1 Quality Gate (milestone: {milestone}) ===\n")
    result = run_quality_gate(milestone=milestone)

    for name, ok in result.checks.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    if result.weaknesses:
        print("\nWeaknesses:")
        for w in result.weaknesses:
            print(f"  - {w}")

    print(f"\nReport: {result.report_path}")

    if result.passed:
        print("\nPASS: Quality gate cleared.")
        sys.exit(0)

    print("\nFAIL: Quality gate blocked. Fix weaknesses before proceeding.")
    sys.exit(1)


if __name__ == "__main__":
    main()

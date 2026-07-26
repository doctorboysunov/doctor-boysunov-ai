"""Run Universal Medical Brain multi-specialty evaluation."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ.setdefault("OPENAI_API_KEY", "eval-test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "eval-test")

from app.medical_brain.evaluation import SCENARIOS, evaluate_all_scenarios  # noqa: E402
from app.medical_brain.specialties.registry import get_all_specialties  # noqa: E402


def main() -> None:
    results = evaluate_all_scenarios()
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    specialties = len(get_all_specialties())

    print(f"\n=== Universal Medical Brain Evaluation ===")
    print(f"Specialties registered: {specialties}")
    print(f"Scenarios: {passed}/{total} ({round(passed/total*100, 1)}%)\n")

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.scenario_id}: {r.title}")
        print(f"       Routed: {r.routing_primary} + {r.routing_secondary}")
        if not r.passed:
            failed = [k for k, v in r.checks.items() if not v]
            print(f"       Failed: {failed}")
        print()

    report_path = ROOT / "data" / "medical_brain_eval.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Report: {report_path}")

    if passed < total:
        sys.exit(1)
    print("PASS: Universal Medical Brain evaluation complete.")


if __name__ == "__main__":
    main()

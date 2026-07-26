"""Phase 11 — Production Clinical AI verification."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ.setdefault("OPENAI_API_KEY", "eval-test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "eval-test")


def main() -> None:
    scripts = [
        "scripts/run_clinical_evaluation.py",
        "scripts/evaluate_clinical_brain_20_scenarios.py",
        "scripts/verify_step_10_7.py",
    ]
    for script in scripts:
        print(f"\n--- Running {script} ---")
        result = subprocess.run(
            [sys.executable, str(ROOT / script)],
            cwd=ROOT,
            check=False,
        )
        if result.returncode != 0:
            print(f"\nFAIL: {script} exited {result.returncode}")
            sys.exit(result.returncode)

    print("\n=== Phase 11 Production Clinical AI: ALL CHECKS PASSED ===")


if __name__ == "__main__":
    main()

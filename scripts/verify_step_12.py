"""Phase 12 — Universal Medical Brain verification."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ.setdefault("OPENAI_API_KEY", "eval-test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "eval-test")


def main() -> None:
    scripts = [
        "scripts/run_medical_evaluation.py",
        "scripts/run_clinical_evaluation.py",
        "scripts/verify_step_10_7.py",
    ]
    for script in scripts:
        print(f"\n--- Running {script} ---")
        result = subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=False)
        if result.returncode != 0:
            print(f"\nFAIL: {script} exited {result.returncode}")
            sys.exit(result.returncode)

    from app.medical_brain.specialties.registry import get_all_specialties  # noqa: E402

    count = len(get_all_specialties())
    print(f"\n=== Phase 12 Universal Medical Brain: ALL CHECKS PASSED ({count} specialties) ===")


if __name__ == "__main__":
    main()

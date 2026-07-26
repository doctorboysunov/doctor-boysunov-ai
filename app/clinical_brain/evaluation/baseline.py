"""Baseline comparison for continuous improvement (Phase 11)."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_BASELINE_PATH = Path(__file__).resolve().parents[3] / "data" / "clinical_eval_baseline.json"


def load_baseline(path: Path | None = None) -> dict | None:
    p = path or DEFAULT_BASELINE_PATH
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_baseline(score_percent: float, passed: int, total: int, *, path: Path | None = None) -> None:
    p = path or DEFAULT_BASELINE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "score_percent": score_percent,
                "passed": passed,
                "total": total,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def compare_to_baseline(
    score_percent: float,
    *,
    path: Path | None = None,
    min_regression_tolerance: float = 0.0,
) -> tuple[bool, str]:
    """Return (passes_gate, message). Fails if score dropped below baseline."""
    baseline = load_baseline(path)
    if baseline is None:
        return True, "No baseline yet — current run will become baseline."
    base_score = float(baseline.get("score_percent", 0))
    if score_percent + min_regression_tolerance < base_score:
        return False, (
            f"REGRESSION: score {score_percent}% is below baseline {base_score}%. "
            "Do not deploy until quality is restored."
        )
    if score_percent > base_score:
        return True, f"IMPROVED: {score_percent}% vs baseline {base_score}%."
    return True, f"STABLE: {score_percent}% matches baseline {base_score}%."

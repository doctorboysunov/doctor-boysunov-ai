#!/usr/bin/env python3
"""Phase 2.2 — Evidence-based clinical validation against trusted guidelines."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.medical_brain.evidence.catalog import all_sources
from app.medical_brain.evidence.reporter import write_batch_summary
from app.medical_brain.evidence.validate_case import validate_batch_evidence
from app.medical_brain.training.evaluator import evaluate_batch
from app.medical_brain.training.generator import generate_case, total_case_capacity
from app.medical_brain.training.loop import sample_case_indices


def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence-based clinical validation")
    parser.add_argument("--sample", type=int, default=200, help="Cases to validate")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print("\n=== Evidence-Based Clinical Validation (Phase 2.2) ===")
    print(f"Guideline sources: {', '.join(all_sources())}")
    print(f"Sample: {args.sample} cases from {total_case_capacity():,} bank\n")

    indices = sample_case_indices(total_case_capacity(), args.sample, args.seed)
    cases = [generate_case(i) for i in indices]
    results = evaluate_batch(cases)
    reports = validate_batch_evidence(cases, results)

    passed = sum(1 for r in reports if r.passed)
    avg = round(sum(r.agreement_score for r in reports) / len(reports), 2) if reports else 0
    write_batch_summary(reports)

    print(f"Validated: {len(reports)}")
    print(f"Evidence pass rate: {round(100 * passed / len(reports), 1)}%")
    print(f"Avg agreement score: {avg}%")
    print(f"Disagreements logged: data/training/evidence/disagreements.jsonl")
    print(f"Report: data/training/evidence/evidence_validation_report.md")

    return 0 if avg >= 75 else 1


if __name__ == "__main__":
    raise SystemExit(main())

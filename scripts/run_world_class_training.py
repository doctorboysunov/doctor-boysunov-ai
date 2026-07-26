#!/usr/bin/env python3
"""World-class Medical Brain training loop — generate, blind-evaluate, optimize."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.medical_brain.training.generator import total_case_capacity, verify_capacity
from app.medical_brain.training.loop import run_training_evaluation
from app.medical_brain.training.types import PRODUCTION_QUALITY


def main() -> int:
    parser = argparse.ArgumentParser(description="World-class Medical Brain training evaluation")
    parser.add_argument("--sample", type=int, default=2000, help="Sample size for blind evaluation")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    parser.add_argument("--iterations", type=int, default=1, help="Optimization iterations")
    args = parser.parse_args()

    cap = total_case_capacity()
    print(f"\n=== World-Class Medical Brain Training ===")
    print(f"Case bank capacity: {cap:,} unique cases")
    print(f"100k target: {'PASS' if verify_capacity(100_000) else 'FAIL'}")
    print(f"Blind evaluation sample: {args.sample:,}")
    print(f"Production thresholds: {PRODUCTION_QUALITY}\n")

    report = run_training_evaluation(
        sample_size=args.sample,
        seed=args.seed,
        max_iterations=args.iterations,
    )

    print(f"\nEvaluated: {report.evaluated:,}")
    print(f"Pass rate: {report.pass_rate}%")
    print(f"Reasoning accuracy: {report.metric_averages.reasoning_accuracy}%")
    print(f"Patient safety: {report.metric_averages.patient_safety}%")
    print(f"Specialty routing: {report.metric_averages.specialty_routing}%")
    print(f"Red flag detection: {report.metric_averages.red_flag_detection}%")
    print(f"Overall: {report.metric_averages.overall}%")
    print(f"\nProduction ready: {'YES' if report.production_ready else 'NO — continue optimization'}")
    print(f"Report: data/training/world_class_report.md")

    if not report.production_ready:
        print("\nOptimization suggestions saved to data/training/optimization_suggestions.json")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

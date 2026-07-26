#!/usr/bin/env python3
"""Phase 2.1 — Continuous Clinical Learning cycle."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.medical_brain.training.continuous_loop import run_continuous_learning_cycle
from app.medical_brain.training.generator import total_case_capacity


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuous clinical learning cycle")
    parser.add_argument("--sample", type=int, default=1000, help="Cases to evaluate this cycle")
    parser.add_argument("--seed", type=int, default=42, help="Random sample seed")
    parser.add_argument("--max-retries", type=int, default=5, help="Max retries per failed case")
    args = parser.parse_args()

    print(f"\n=== Continuous Clinical Learning (Phase 2.1) ===")
    print(f"Case bank capacity: {total_case_capacity():,}")
    print(f"Sample size: {args.sample:,}")
    print(f"Max retries per failure: {args.max_retries}\n")

    cycle, dashboard = run_continuous_learning_cycle(
        sample_size=args.sample,
        seed=args.seed,
        max_retries=args.max_retries,
    )

    print(f"Cycle {cycle.cycle_id} complete")
    print(f"  Pass rate: {cycle.pass_rate}%")
    print(f"  Reasoning accuracy: {cycle.metrics.get('reasoning_accuracy')}%")
    print(f"  Differential diagnosis: {cycle.metrics.get('differential_diagnosis')}%")
    print(f"  Red-flag detection: {cycle.metrics.get('red_flag_detection')}%")
    print(f"  Specialty routing: {cycle.metrics.get('specialty_routing')}%")
    print(f"  Safety score: {cycle.metrics.get('patient_safety')}% (delta: {cycle.safety_delta:+.2f})")
    print(f"  Avg questions: {cycle.avg_questions}")
    print(f"  Failed cases saved: {cycle.failed}")
    print(f"  Still failing after retry: {len(cycle.recurring_failures)}")
    print(f"  Patches recorded: {len(cycle.patches_applied)}")
    print(f"\n  Optimization complete: {'YES' if cycle.optimization_complete else 'NO'}")
    print(f"\nDashboard: data/training/clinical_quality_dashboard.md")
    print(f"Failures:  data/training/failures/failures.jsonl")
    print(f"History:   data/training/history/cycle_{cycle.cycle_id:04d}.json")

    return 0 if cycle.optimization_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())

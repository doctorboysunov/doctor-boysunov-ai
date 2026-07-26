#!/usr/bin/env python3
"""Clinical Reasoning Benchmark — 10,000+ cases, all specialties, deployment gate."""

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

from app.medical_brain.evaluation.benchmark.aggregator import build_benchmark_report
from app.medical_brain.evaluation.benchmark.dashboard import write_benchmark_dashboard
from app.medical_brain.evaluation.benchmark.evaluator import evaluate_benchmark_case
from app.medical_brain.evaluation.benchmark.types import BENCHMARK_TARGET_CASES, BENCHMARK_THRESHOLDS
from app.medical_brain.training.generator import generate_case, total_case_capacity, verify_capacity
from app.medical_brain.training.loop import sample_case_indices


def main() -> int:
    parser = argparse.ArgumentParser(description="Clinical Reasoning Benchmark")
    parser.add_argument("--sample", type=int, default=BENCHMARK_TARGET_CASES, help="Cases to evaluate")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--verify-only", action="store_true", help="Verify case bank capacity only")
    args = parser.parse_args()

    cap = total_case_capacity()
    print("\n=== Clinical Reasoning Benchmark ===")
    print(f"Case bank capacity: {cap:,}")
    print(f"Target sample: {args.sample:,}")
    print(f"Production thresholds: {BENCHMARK_THRESHOLDS}\n")

    if args.verify_only:
        ok = verify_capacity()
        print(f"Capacity verification: {'PASS' if ok else 'FAIL'} ({cap:,} cases)")
        return 0 if ok and cap >= BENCHMARK_TARGET_CASES else 1

    if cap < BENCHMARK_TARGET_CASES:
        print(f"FAIL: Case bank {cap:,} < {BENCHMARK_TARGET_CASES:,} required")
        return 1

    sample = min(args.sample, cap)
    indices = sample_case_indices(cap, sample, args.seed)
    specialties_seen: set[str] = set()

    results = []
    for i, idx in enumerate(indices, 1):
        case = generate_case(idx)
        specialties_seen.add(case.specialty)
        result = evaluate_benchmark_case(case)
        results.append(result)
        if i % 500 == 0 or i == sample:
            av = build_benchmark_report(results, target_cases=sample).metric_averages
            print(
                f"  Progress: {i:,}/{sample:,} — "
                f"DD {av.differential_diagnosis_accuracy}% | "
                f"EM {av.emergency_recognition_accuracy}% | "
                f"GA {av.guideline_agreement}% | "
                f"pass {round(100*sum(1 for r in results if r.passed)/len(results),1)}%"
            )

    report = build_benchmark_report(results, target_cases=sample)
    json_path, md_path = write_benchmark_dashboard(report, results)

    av = report.metric_averages
    print(f"\nEvaluated: {report.evaluated:,} cases across {len(specialties_seen)} specialties")
    print(f"Pass rate: {report.pass_rate}%")
    print("\nBenchmark metrics:")
    for metric in (
        "differential_diagnosis_accuracy",
        "emergency_recognition_accuracy",
        "next_question_quality",
        "guideline_agreement",
        "hallucination_rate",
        "missing_critical_diagnosis_rate",
        "false_reassurance_rate",
        "referral_accuracy",
    ):
        val = getattr(av, metric)
        print(f"  {metric}: {val}%")

    print(f"\nProduction ready: {'YES' if report.production_ready else 'NO'}")
    print(f"Deployment allowed: {'YES' if report.deployment_allowed else 'NO — BLOCKED'}")
    print(f"\nDashboard: {md_path}")
    print(f"JSON: {json_path}")

    if not report.deployment_allowed:
        print("\nFAIL: Benchmark below production threshold — DO NOT DEPLOY.")
        gaps = {k: v for k, v in report.threshold_gaps.items() if v > 0}
        for metric, gap in gaps.items():
            print(f"  - {metric}: {gap}% gap")
        return 1

    print("\nPASS: All benchmark metrics meet production thresholds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Training loop — generate, blind-evaluate, optimize until production quality."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Iterator

from app.medical_brain.training.evaluator import evaluate_batch
from app.medical_brain.training.failure_store import save_failed_case
from app.medical_brain.training.generator import generate_case, total_case_capacity
from app.medical_brain.training.optimizer import (
    analyze_failures,
    apply_safe_patches,
    aggregate_metrics,
    check_production_ready,
    generate_patches,
    save_suggestions,
)
from app.medical_brain.training.reporter import write_training_report
from app.medical_brain.training.types import GeneratedClinicalCase, TrainingReport


def sample_case_indices(total: int, sample_size: int, seed: int = 42) -> list[int]:
    """Stratified random sample across full case bank."""
    cap = total_case_capacity()
    n = min(sample_size, cap)
    rng = random.Random(seed)
    return sorted(rng.sample(range(cap), n))


def run_training_evaluation(
    *,
    sample_size: int = 2000,
    seed: int = 42,
    max_iterations: int = 3,
) -> TrainingReport:
    """Run blind evaluation on a sample and optimization cycle."""
    cap = total_case_capacity()
    indices = sample_case_indices(cap, sample_size, seed)
    all_results = []
    last_patches: list[str] = []

    for iteration in range(max_iterations):
        cases = [generate_case(i) for i in indices]
        results = evaluate_batch(cases)
        for case, result in zip(cases, results):
            if not result.passed:
                save_failed_case(case, result, cycle_id=iteration + 1)
        all_results = results

        clusters = analyze_failures(results)
        patches = generate_patches(clusters, results)
        applied = apply_safe_patches(patches)
        last_patches = applied
        save_suggestions(patches, clusters)

        averages = aggregate_metrics(results)
        if check_production_ready(averages):
            break
        # Subsequent iterations re-evaluate same indices (router/prompt may improve)
        if not applied and iteration > 0:
            break

    passed = sum(1 for r in all_results if r.passed)
    failed = len(all_results) - passed
    averages = aggregate_metrics(all_results)

    by_spec: dict[str, dict[str, float]] = {}
    for r in all_results:
        if r.specialty not in by_spec:
            by_spec[r.specialty] = {"passed": 0, "failed": 0, "scores": []}
        if r.passed:
            by_spec[r.specialty]["passed"] += 1
        else:
            by_spec[r.specialty]["failed"] += 1
        by_spec[r.specialty]["scores"].append(r.scores.overall)

    for spec, data in by_spec.items():
        scores = data["scores"]
        data["avg_score"] = round(sum(scores) / len(scores), 2) if scores else 0
        total = data["passed"] + data["failed"]
        data["pass_rate"] = round(100 * data["passed"] / total, 1) if total else 0
        del data["scores"]

    clusters = analyze_failures(all_results)
    patches = generate_patches(clusters, all_results)
    production_ready = check_production_ready(averages)

    report = TrainingReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_cases=cap,
        evaluated=len(all_results),
        passed=passed,
        failed=failed,
        pass_rate=round(100 * passed / len(all_results), 2) if all_results else 0,
        metric_averages=averages,
        by_specialty=by_spec,
        recurring_failures=[(c.failure_type, c.count) for c in clusters[:10]],
        optimization_patches=[p.to_dict() for p in patches[:15]],
        production_ready=production_ready,
        requires_improvement=not production_ready,
    )
    write_training_report(report, all_results)
    return report

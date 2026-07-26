"""Clinical Reasoning Benchmark — aggregate results and production gate."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from app.medical_brain.evaluation.benchmark.types import (
    BENCHMARK_METRICS,
    BENCHMARK_THRESHOLDS,
    BenchmarkCaseResult,
    BenchmarkMetricScores,
    BenchmarkReport,
)


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def aggregate_benchmark_results(results: list[BenchmarkCaseResult]) -> BenchmarkMetricScores:
    if not results:
        return BenchmarkMetricScores()
    return BenchmarkMetricScores(
        differential_diagnosis_accuracy=_avg([r.scores.differential_diagnosis_accuracy for r in results]),
        emergency_recognition_accuracy=_avg([r.scores.emergency_recognition_accuracy for r in results]),
        next_question_quality=_avg([r.scores.next_question_quality for r in results]),
        guideline_agreement=_avg([r.scores.guideline_agreement for r in results]),
        hallucination_rate=_avg([r.scores.hallucination_rate for r in results]),
        missing_critical_diagnosis_rate=_avg([r.scores.missing_critical_diagnosis_rate for r in results]),
        false_reassurance_rate=_avg([r.scores.false_reassurance_rate for r in results]),
        referral_accuracy=_avg([r.scores.referral_accuracy for r in results]),
    )


def compute_threshold_gaps(averages: BenchmarkMetricScores) -> dict[str, float]:
    """Positive gap = below threshold (needs improvement)."""
    gaps: dict[str, float] = {}
    gaps["differential_diagnosis_accuracy"] = round(
        BENCHMARK_THRESHOLDS["differential_diagnosis_accuracy"] - averages.differential_diagnosis_accuracy, 2
    )
    gaps["emergency_recognition_accuracy"] = round(
        BENCHMARK_THRESHOLDS["emergency_recognition_accuracy"] - averages.emergency_recognition_accuracy, 2
    )
    gaps["next_question_quality"] = round(
        BENCHMARK_THRESHOLDS["next_question_quality"] - averages.next_question_quality, 2
    )
    gaps["guideline_agreement"] = round(
        BENCHMARK_THRESHOLDS["guideline_agreement"] - averages.guideline_agreement, 2
    )
    gaps["hallucination_rate"] = round(
        averages.hallucination_rate - BENCHMARK_THRESHOLDS["hallucination_rate_max"], 2
    )
    gaps["missing_critical_diagnosis_rate"] = round(
        averages.missing_critical_diagnosis_rate - BENCHMARK_THRESHOLDS["missing_critical_diagnosis_rate_max"], 2
    )
    gaps["false_reassurance_rate"] = round(
        averages.false_reassurance_rate - BENCHMARK_THRESHOLDS["false_reassurance_rate_max"], 2
    )
    gaps["referral_accuracy"] = round(
        BENCHMARK_THRESHOLDS["referral_accuracy"] - averages.referral_accuracy, 2
    )
    return gaps


def check_benchmark_production_ready(averages: BenchmarkMetricScores, pass_rate: float) -> bool:
    """Return True only when every aggregate metric meets production threshold."""
    _ = pass_rate  # tracked in dashboard; gate uses metric averages
    if averages.differential_diagnosis_accuracy < BENCHMARK_THRESHOLDS["differential_diagnosis_accuracy"]:
        return False
    if averages.emergency_recognition_accuracy < BENCHMARK_THRESHOLDS["emergency_recognition_accuracy"]:
        return False
    if averages.next_question_quality < BENCHMARK_THRESHOLDS["next_question_quality"]:
        return False
    if averages.guideline_agreement < BENCHMARK_THRESHOLDS["guideline_agreement"]:
        return False
    if averages.hallucination_rate > BENCHMARK_THRESHOLDS["hallucination_rate_max"]:
        return False
    if averages.missing_critical_diagnosis_rate > BENCHMARK_THRESHOLDS["missing_critical_diagnosis_rate_max"]:
        return False
    if averages.false_reassurance_rate > BENCHMARK_THRESHOLDS["false_reassurance_rate_max"]:
        return False
    if averages.referral_accuracy < BENCHMARK_THRESHOLDS["referral_accuracy"]:
        return False
    return True


def build_benchmark_report(results: list[BenchmarkCaseResult], *, target_cases: int) -> BenchmarkReport:
    evaluated = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = evaluated - passed
    pass_rate = round(100 * passed / evaluated, 2) if evaluated else 0.0
    averages = aggregate_benchmark_results(results)
    gaps = compute_threshold_gaps(averages)
    production_ready = check_benchmark_production_ready(averages, pass_rate)

    by_specialty: dict[str, dict[str, float]] = {}
    by_category: dict[str, dict[str, float]] = {}
    for r in results:
        for bucket, key in ((by_specialty, r.specialty), (by_category, r.category)):
            if key not in bucket:
                bucket[key] = {"passed": 0, "failed": 0, "scores": []}
            if r.passed:
                bucket[key]["passed"] += 1
            else:
                bucket[key]["failed"] += 1
            bucket[key]["scores"].append(r.scores.overall)

    for bucket in (by_specialty, by_category):
        for key, data in bucket.items():
            scores = data["scores"]
            total = data["passed"] + data["failed"]
            data["pass_rate"] = round(100 * data["passed"] / total, 1) if total else 0
            data["avg_overall"] = _avg(scores)
            del data["scores"]

    failure_counter: Counter[str] = Counter()
    for r in results:
        if not r.passed:
            for reason in r.failure_reasons[:2]:
                failure_counter[reason[:80]] += 1

    return BenchmarkReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        target_cases=target_cases,
        evaluated=evaluated,
        passed=passed,
        failed=failed,
        pass_rate=pass_rate,
        metric_averages=averages,
        by_specialty=by_specialty,
        by_category=by_category,
        recurring_failures=failure_counter.most_common(15),
        production_ready=production_ready,
        deployment_allowed=production_ready,
        threshold_gaps=gaps,
    )

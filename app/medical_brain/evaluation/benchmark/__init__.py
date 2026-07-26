"""Clinical Reasoning Benchmark — 10,000+ case evaluation across all specialties."""

from app.medical_brain.evaluation.benchmark.aggregator import (
    aggregate_benchmark_results,
    build_benchmark_report,
    check_benchmark_production_ready,
    compute_threshold_gaps,
)
from app.medical_brain.evaluation.benchmark.dashboard import write_benchmark_dashboard
from app.medical_brain.evaluation.benchmark.evaluator import evaluate_benchmark_batch, evaluate_benchmark_case
from app.medical_brain.evaluation.benchmark.types import (
    BENCHMARK_TARGET_CASES,
    BENCHMARK_THRESHOLDS,
    BenchmarkReport,
)

__all__ = [
    "BENCHMARK_TARGET_CASES",
    "BENCHMARK_THRESHOLDS",
    "BenchmarkReport",
    "aggregate_benchmark_results",
    "build_benchmark_report",
    "check_benchmark_production_ready",
    "compute_threshold_gaps",
    "evaluate_benchmark_batch",
    "evaluate_benchmark_case",
    "write_benchmark_dashboard",
]

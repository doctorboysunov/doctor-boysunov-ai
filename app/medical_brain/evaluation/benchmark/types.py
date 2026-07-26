"""Clinical Reasoning Benchmark — types and production thresholds."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BENCHMARK_TARGET_CASES = 10_000
BENCHMARK_MIN_SPECIALTIES = 23

# Production thresholds — deployment blocked until ALL are met
BENCHMARK_THRESHOLDS = {
    "differential_diagnosis_accuracy": 95.0,
    "emergency_recognition_accuracy": 95.0,
    "next_question_quality": 90.0,
    "guideline_agreement": 75.0,
    "hallucination_rate_max": 2.0,  # max failure % (lower is better)
    "missing_critical_diagnosis_rate_max": 3.0,
    "false_reassurance_rate_max": 2.0,
    "referral_accuracy": 90.0,
    "overall_pass_rate": 92.0,
}

BENCHMARK_METRICS = (
    "differential_diagnosis_accuracy",
    "emergency_recognition_accuracy",
    "next_question_quality",
    "guideline_agreement",
    "hallucination_rate",
    "missing_critical_diagnosis_rate",
    "false_reassurance_rate",
    "referral_accuracy",
)


@dataclass
class BenchmarkMetricScores:
    differential_diagnosis_accuracy: float = 0.0
    emergency_recognition_accuracy: float = 0.0
    next_question_quality: float = 0.0
    guideline_agreement: float = 0.0
    hallucination_rate: float = 0.0  # failure rate 0-100
    missing_critical_diagnosis_rate: float = 0.0
    false_reassurance_rate: float = 0.0
    referral_accuracy: float = 0.0

    @property
    def overall(self) -> float:
        # Inverted rates: score = 100 - failure_rate for aggregation
        inv = (
            self.differential_diagnosis_accuracy
            + self.emergency_recognition_accuracy
            + self.next_question_quality
            + self.guideline_agreement
            + (100.0 - self.hallucination_rate)
            + (100.0 - self.missing_critical_diagnosis_rate)
            + (100.0 - self.false_reassurance_rate)
            + self.referral_accuracy
        )
        return round(inv / 8, 2)

    def to_dict(self) -> dict[str, float]:
        d = {m: getattr(self, m) for m in BENCHMARK_METRICS}
        d["overall"] = self.overall
        return d


@dataclass
class BenchmarkCaseResult:
    case_id: str
    specialty: str
    category: str
    gold_diagnosis: str
    passed: bool
    scores: BenchmarkMetricScores
    checks: dict[str, bool] = field(default_factory=dict)
    failure_reasons: list[str] = field(default_factory=list)
    routing_primary: str = ""
    routing_secondary: list[str] = field(default_factory=list)
    missed_red_flags: list[str] = field(default_factory=list)
    evidence_agreement: float = 0.0
    ranked_top3: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "specialty": self.specialty,
            "category": self.category,
            "gold_diagnosis": self.gold_diagnosis,
            "passed": self.passed,
            "scores": self.scores.to_dict(),
            "checks": self.checks,
            "failure_reasons": self.failure_reasons,
            "routing_primary": self.routing_primary,
            "routing_secondary": self.routing_secondary,
            "missed_red_flags": self.missed_red_flags,
            "evidence_agreement": self.evidence_agreement,
            "ranked_top3": self.ranked_top3,
        }


@dataclass
class BenchmarkReport:
    timestamp: str = ""
    target_cases: int = BENCHMARK_TARGET_CASES
    evaluated: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    metric_averages: BenchmarkMetricScores = field(default_factory=BenchmarkMetricScores)
    by_specialty: dict[str, dict[str, float]] = field(default_factory=dict)
    by_category: dict[str, dict[str, float]] = field(default_factory=dict)
    recurring_failures: list[tuple[str, int]] = field(default_factory=list)
    production_ready: bool = False
    deployment_allowed: bool = False
    threshold_gaps: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "target_cases": self.target_cases,
            "evaluated": self.evaluated,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "metric_averages": self.metric_averages.to_dict(),
            "by_specialty": self.by_specialty,
            "by_category": self.by_category,
            "recurring_failures": self.recurring_failures,
            "production_ready": self.production_ready,
            "deployment_allowed": self.deployment_allowed,
            "threshold_gaps": self.threshold_gaps,
            "thresholds": BENCHMARK_THRESHOLDS,
        }

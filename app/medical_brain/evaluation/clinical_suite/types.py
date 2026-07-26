"""Clinical Evaluation Suite — domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PASS_THRESHOLD = 99.0

SCORE_DIMENSIONS = (
    "clinical_reasoning",
    "safety",
    "conversation_quality",
    "diagnostic_accuracy",
    "referral_accuracy",
)


@dataclass
class ClinicalCase:
    id: str
    specialty: str
    title: str
    opening_message: str
    expected_primary: str
    expected_secondary: list[str] = field(default_factory=list)
    expected_reasoning: str = ""
    expected_red_flags: list[str] = field(default_factory=list)
    forbidden_questions: list[str] = field(default_factory=list)
    expected_differentials: list[str] = field(default_factory=list)
    expected_referral: str = ""
    requires_emergency: bool = False
    requires_multi_specialty: bool = False
    expert_priority_phase: str = "narrative"
    common_ai_mistake: str = ""
    improvement_hint: str = ""


@dataclass
class DimensionScores:
    clinical_reasoning: float = 0.0
    safety: float = 0.0
    conversation_quality: float = 0.0
    diagnostic_accuracy: float = 0.0
    referral_accuracy: float = 0.0

    @property
    def overall(self) -> float:
        values = [
            self.clinical_reasoning,
            self.safety,
            self.conversation_quality,
            self.diagnostic_accuracy,
            self.referral_accuracy,
        ]
        return round(sum(values) / len(values), 2)

    def to_dict(self) -> dict[str, float]:
        return {
            "clinical_reasoning": self.clinical_reasoning,
            "safety": self.safety,
            "conversation_quality": self.conversation_quality,
            "diagnostic_accuracy": self.diagnostic_accuracy,
            "referral_accuracy": self.referral_accuracy,
            "overall": self.overall,
        }


@dataclass
class CaseEvaluation:
    case_id: str
    title: str
    specialty: str
    passed: bool
    scores: DimensionScores
    routing_primary: str
    routing_secondary: list[str]
    detected_red_flags: list[str]
    mode: str  # structural | live | combined
    missed_red_flags: list[str] = field(default_factory=list)
    unnecessary_questions: list[str] = field(default_factory=list)
    ai_reasoning_summary: str = ""
    expected_reasoning: str = ""
    improvement_actions: list[str] = field(default_factory=list)
    live_patient_reply: str = ""
    checks: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "specialty": self.specialty,
            "passed": self.passed,
            "scores": self.scores.to_dict(),
            "routing_primary": self.routing_primary,
            "routing_secondary": self.routing_secondary,
            "detected_red_flags": self.detected_red_flags,
            "mode": self.mode,
            "missed_red_flags": self.missed_red_flags,
            "unnecessary_questions": self.unnecessary_questions,
            "ai_reasoning_summary": self.ai_reasoning_summary,
            "expected_reasoning": self.expected_reasoning,
            "improvement_actions": self.improvement_actions,
            "live_patient_reply": self.live_patient_reply,
            "checks": self.checks,
        }


@dataclass
class SuiteReport:
    timestamp: str = ""
    mode: str = "structural"
    total_cases: int = 0
    evaluated: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    overall_score: float = 0.0
    dimension_averages: DimensionScores = field(default_factory=DimensionScores)
    by_specialty: dict[str, dict[str, float]] = field(default_factory=dict)
    pass_threshold: float = PASS_THRESHOLD
    passed_suite: bool = False
    requires_improvement: bool = False
    improvement_actions: list[str] = field(default_factory=list)
    live_evaluated: int = 0
    structural_evaluated: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "mode": self.mode,
            "total_cases": self.total_cases,
            "evaluated": self.evaluated,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "overall_score": self.overall_score,
            "dimension_averages": self.dimension_averages.to_dict(),
            "by_specialty": self.by_specialty,
            "pass_threshold": self.pass_threshold,
            "passed_suite": self.passed_suite,
            "requires_improvement": self.requires_improvement,
            "improvement_actions": self.improvement_actions,
            "live_evaluated": self.live_evaluated,
            "structural_evaluated": self.structural_evaluated,
        }

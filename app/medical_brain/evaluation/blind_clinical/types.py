"""Blind Clinical Reasoning Evaluation — domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TARGET_TOTAL = 1000
CLINICAL_REASONING_PASS = 99.0
CASE_PASS_THRESHOLD = 90.0

BLIND_METRICS = (
    "history_taking_quality",
    "clinical_reasoning",
    "differential_diagnosis",
    "red_flag_detection",
    "safety",
    "specialty_routing",
    "follow_up_questions",
    "final_recommendation",
)

CASE_CATEGORIES = (
    "common",
    "rare",
    "multi_disease",
    "misleading",
    "emergency",
    "pediatric",
    "adult",
    "elderly",
    "pregnancy",
    "oncology",
    "infectious",
)


@dataclass
class BlindTurn:
    role: str  # user | assistant
    content: str


@dataclass
class BlindCase:
    """Patient-facing data is visible to engine; ground_truth is scorer-only."""

    id: str
    category: str
    age_group: str  # pediatric | adult | elderly
    patient_profile: str  # demographics only — never diagnosis
    turns: list[BlindTurn]
    # --- Hidden ground truth (NEVER sent to Medical Brain) ---
    expected_primary: str = ""
    expected_secondary: list[str] = field(default_factory=list)
    expected_differentials: list[str] = field(default_factory=list)
    expected_red_flags: list[str] = field(default_factory=list)
    requires_emergency: bool = False
    expected_recommendation: str = ""
    reasoning_rubric: str = ""

    @property
    def opening_message(self) -> str:
        for turn in self.turns:
            if turn.role == "user":
                return turn.content
        return self.turns[0].content if self.turns else ""

    @property
    def full_patient_text(self) -> str:
        return " ".join(t.content for t in self.turns if t.role == "user")


@dataclass
class BlindScores:
    history_taking_quality: float = 0.0
    clinical_reasoning: float = 0.0
    differential_diagnosis: float = 0.0
    red_flag_detection: float = 0.0
    safety: float = 0.0
    specialty_routing: float = 0.0
    follow_up_questions: float = 0.0
    final_recommendation: float = 0.0

    @property
    def overall(self) -> float:
        values = [getattr(self, m) for m in BLIND_METRICS]
        return round(sum(values) / len(values), 2)

    def to_dict(self) -> dict[str, float]:
        d = {m: getattr(self, m) for m in BLIND_METRICS}
        d["overall"] = self.overall
        return d


@dataclass
class BlindCaseResult:
    case_id: str
    category: str
    age_group: str
    passed: bool
    scores: BlindScores
    routing_primary: str
    routing_secondary: list[str]
    detected_red_flags: list[str]
    missed_red_flags: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)
    improvement_actions: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "age_group": self.age_group,
            "passed": self.passed,
            "scores": self.scores.to_dict(),
            "routing_primary": self.routing_primary,
            "routing_secondary": self.routing_secondary,
            "detected_red_flags": self.detected_red_flags,
            "missed_red_flags": self.missed_red_flags,
            "failure_reasons": self.failure_reasons,
            "improvement_actions": self.improvement_actions,
            "checks": self.checks,
        }


@dataclass
class BlindReport:
    timestamp: str = ""
    total_cases: int = TARGET_TOTAL
    evaluated: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    overall_score: float = 0.0
    clinical_reasoning_average: float = 0.0
    metric_averages: BlindScores = field(default_factory=BlindScores)
    by_category: dict[str, dict[str, float]] = field(default_factory=dict)
    by_age_group: dict[str, dict[str, float]] = field(default_factory=dict)
    recurring_mistakes: list[tuple[str, int]] = field(default_factory=list)
    concrete_fixes: list[str] = field(default_factory=list)
    passed_suite: bool = False
    requires_improvement: bool = False
    clinical_reasoning_threshold: float = CLINICAL_REASONING_PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_cases": self.total_cases,
            "evaluated": self.evaluated,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "overall_score": self.overall_score,
            "clinical_reasoning_average": self.clinical_reasoning_average,
            "metric_averages": self.metric_averages.to_dict(),
            "by_category": self.by_category,
            "by_age_group": self.by_age_group,
            "recurring_mistakes": self.recurring_mistakes,
            "concrete_fixes": self.concrete_fixes,
            "passed_suite": self.passed_suite,
            "requires_improvement": self.requires_improvement,
            "clinical_reasoning_threshold": self.clinical_reasoning_threshold,
        }

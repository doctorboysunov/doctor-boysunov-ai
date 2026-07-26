"""Doctor-level Clinical Challenge — domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PASS_THRESHOLD = 98.0
CASE_PASS_THRESHOLD = 90.0
TARGET_TOTAL = 100

CHALLENGE_METRICS = (
    "clinical_reasoning",
    "differential_diagnosis_quality",
    "question_selection",
    "safety",
    "red_flag_detection",
    "specialty_routing",
    "physician_similarity",
)

CASE_CATEGORIES = (
    "emergency",
    "common",
    "rare",
    "chronic_followup",
    "multi_complaint",
    "misinformation",
    "interruption",
    "hidden_red_flag",
)


@dataclass
class ConversationTurn:
    role: str  # user | assistant
    content: str
    is_interruption: bool = False
    contains_misinformation: bool = False


@dataclass
class ChallengeCase:
    id: str
    title: str
    specialty: str
    category: str
    patient_profile: str
    turns: list[ConversationTurn]
    expected_primary: str
    expected_secondary: list[str] = field(default_factory=list)
    expected_red_flags: list[str] = field(default_factory=list)
    expected_differentials: list[str] = field(default_factory=list)
    requires_emergency: bool = False
    hidden_red_flag: str = ""
    patient_misinformation: str = ""
    expected_reasoning: str = ""
    forbidden_questions: list[str] = field(default_factory=list)
    expected_referral: str = ""
    improvement_hint: str = ""

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
class ChallengeScores:
    clinical_reasoning: float = 0.0
    differential_diagnosis_quality: float = 0.0
    question_selection: float = 0.0
    safety: float = 0.0
    red_flag_detection: float = 0.0
    specialty_routing: float = 0.0
    physician_similarity: float = 0.0

    @property
    def overall(self) -> float:
        values = [
            self.clinical_reasoning,
            self.differential_diagnosis_quality,
            self.question_selection,
            self.safety,
            self.red_flag_detection,
            self.specialty_routing,
            self.physician_similarity,
        ]
        return round(sum(values) / len(values), 2)

    def to_dict(self) -> dict[str, float]:
        return {
            "clinical_reasoning": self.clinical_reasoning,
            "differential_diagnosis_quality": self.differential_diagnosis_quality,
            "question_selection": self.question_selection,
            "safety": self.safety,
            "red_flag_detection": self.red_flag_detection,
            "specialty_routing": self.specialty_routing,
            "physician_similarity": self.physician_similarity,
            "overall": self.overall,
        }


@dataclass
class ChallengeCaseResult:
    case_id: str
    title: str
    specialty: str
    category: str
    passed: bool
    scores: ChallengeScores
    mode: str
    routing_primary: str
    routing_secondary: list[str]
    detected_red_flags: list[str]
    missed_red_flags: list[str] = field(default_factory=list)
    unnecessary_questions: list[str] = field(default_factory=list)
    ai_reasoning_summary: str = ""
    ai_patient_reply: str = ""
    failure_reasons: list[str] = field(default_factory=list)
    improvement_actions: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "specialty": self.specialty,
            "category": self.category,
            "passed": self.passed,
            "scores": self.scores.to_dict(),
            "mode": self.mode,
            "routing_primary": self.routing_primary,
            "routing_secondary": self.routing_secondary,
            "detected_red_flags": self.detected_red_flags,
            "missed_red_flags": self.missed_red_flags,
            "unnecessary_questions": self.unnecessary_questions,
            "ai_reasoning_summary": self.ai_reasoning_summary,
            "ai_patient_reply": self.ai_patient_reply,
            "failure_reasons": self.failure_reasons,
            "improvement_actions": self.improvement_actions,
            "checks": self.checks,
        }


@dataclass
class ChallengeReport:
    timestamp: str = ""
    mode: str = "structural"
    total_cases: int = TARGET_TOTAL
    evaluated: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    overall_score: float = 0.0
    metric_averages: ChallengeScores = field(default_factory=ChallengeScores)
    by_specialty: dict[str, dict[str, float]] = field(default_factory=dict)
    by_category: dict[str, dict[str, float]] = field(default_factory=dict)
    pass_threshold: float = PASS_THRESHOLD
    passed_suite: bool = False
    requires_improvement: bool = False
    engine_improvements: list[str] = field(default_factory=list)
    live_evaluated: int = 0

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
            "metric_averages": self.metric_averages.to_dict(),
            "by_specialty": self.by_specialty,
            "by_category": self.by_category,
            "pass_threshold": self.pass_threshold,
            "passed_suite": self.passed_suite,
            "requires_improvement": self.requires_improvement,
            "engine_improvements": self.engine_improvements,
            "live_evaluated": self.live_evaluated,
        }

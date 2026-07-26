"""Real World Validation Suite — domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PASS_THRESHOLD = 90.0

REAL_WORLD_METRICS = (
    "red_flag_detection",
    "emergency_recognition",
    "specialty_routing",
    "follow_up_question_quality",
    "conversation_naturalness",
    "safety",
)


@dataclass
class ConversationTurn:
    role: str  # user | assistant (for replay cases)
    content: str


@dataclass
class RealWorldCase:
    """Anonymized clinical vignette grounded in published guidelines."""

    id: str
    title: str
    specialty: str
    source: str
    patient_profile: str
    turns: list[ConversationTurn]
    guideline_source: str
    guideline_criteria: list[str]
    expert_review: str
    expected_primary: str
    expected_secondary: list[str] = field(default_factory=list)
    expected_red_flags: list[str] = field(default_factory=list)
    requires_emergency: bool = False
    expected_first_question_topics: list[str] = field(default_factory=list)
    forbidden_questions: list[str] = field(default_factory=list)
    expected_referral: str = ""
    failure_risks: list[str] = field(default_factory=list)
    improvement_hint: str = ""

    @property
    def opening_message(self) -> str:
        for turn in self.turns:
            if turn.role == "user":
                return turn.content
        return self.turns[0].content if self.turns else ""


@dataclass
class RealWorldScores:
    red_flag_detection: float = 0.0
    emergency_recognition: float = 0.0
    specialty_routing: float = 0.0
    follow_up_question_quality: float = 0.0
    conversation_naturalness: float = 0.0
    safety: float = 0.0

    @property
    def overall(self) -> float:
        values = [
            self.red_flag_detection,
            self.emergency_recognition,
            self.specialty_routing,
            self.follow_up_question_quality,
            self.conversation_naturalness,
            self.safety,
        ]
        return round(sum(values) / len(values), 2)

    def to_dict(self) -> dict[str, float]:
        return {
            "red_flag_detection": self.red_flag_detection,
            "emergency_recognition": self.emergency_recognition,
            "specialty_routing": self.specialty_routing,
            "follow_up_question_quality": self.follow_up_question_quality,
            "conversation_naturalness": self.conversation_naturalness,
            "safety": self.safety,
            "overall": self.overall,
        }


@dataclass
class RealWorldCaseResult:
    case_id: str
    title: str
    specialty: str
    source: str
    guideline_source: str
    passed: bool
    scores: RealWorldScores
    mode: str
    routing_primary: str
    routing_secondary: list[str]
    detected_red_flags: list[str]
    missed_red_flags: list[str] = field(default_factory=list)
    guideline_gaps: list[str] = field(default_factory=list)
    expert_gaps: list[str] = field(default_factory=list)
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
            "source": self.source,
            "guideline_source": self.guideline_source,
            "passed": self.passed,
            "scores": self.scores.to_dict(),
            "mode": self.mode,
            "routing_primary": self.routing_primary,
            "routing_secondary": self.routing_secondary,
            "detected_red_flags": self.detected_red_flags,
            "missed_red_flags": self.missed_red_flags,
            "guideline_gaps": self.guideline_gaps,
            "expert_gaps": self.expert_gaps,
            "unnecessary_questions": self.unnecessary_questions,
            "ai_reasoning_summary": self.ai_reasoning_summary,
            "ai_patient_reply": self.ai_patient_reply,
            "failure_reasons": self.failure_reasons,
            "improvement_actions": self.improvement_actions,
            "checks": self.checks,
        }


@dataclass
class RealWorldReport:
    timestamp: str = ""
    mode: str = "structural"
    total_cases: int = 0
    evaluated: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    overall_score: float = 0.0
    metric_averages: RealWorldScores = field(default_factory=RealWorldScores)
    by_specialty: dict[str, dict[str, float]] = field(default_factory=dict)
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
            "pass_threshold": self.pass_threshold,
            "passed_suite": self.passed_suite,
            "requires_improvement": self.requires_improvement,
            "engine_improvements": self.engine_improvements,
            "live_evaluated": self.live_evaluated,
        }

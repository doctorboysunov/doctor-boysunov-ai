"""Clinical evaluation domain types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NeurologyScenario:
    id: str
    title: str
    opening_message: str
    category: str
    clinical_label: str
    expert_opens_with: str
    expert_priority_topics: list[str]
    common_ai_mistake: str
    why_ai_mistakes: str
    improvement: str
    requires_triage: bool = False
    requires_override: bool = False
    avoid_patterns: list[str] = field(default_factory=list)


@dataclass
class ScenarioEvaluation:
    scenario_id: str
    title: str
    clinical_label: str
    passed: bool
    score: float
    phase_hint: str
    detected_flags: list[str]
    checks: dict[str, bool]
    expert_opens_with: str
    common_ai_mistake: str
    why_ai_mistakes: str
    improvement: str

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "clinical_label": self.clinical_label,
            "passed": self.passed,
            "score": self.score,
            "phase_hint": self.phase_hint,
            "detected_flags": self.detected_flags,
            "checks": self.checks,
            "expert_opens_with": self.expert_opens_with,
            "common_ai_mistake": self.common_ai_mistake,
            "why_ai_mistakes": self.why_ai_mistakes,
            "improvement": self.improvement,
        }


@dataclass
class EvaluationReport:
    version: str
    total: int
    passed: int
    score_percent: float
    by_category: dict[str, dict[str, float]]
    failures: list[ScenarioEvaluation]
    all_results: list[ScenarioEvaluation]

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "total": self.total,
            "passed": self.passed,
            "score_percent": self.score_percent,
            "by_category": self.by_category,
            "failures": [f.to_dict() for f in self.failures],
            "all_results": [r.to_dict() for r in self.all_results],
        }

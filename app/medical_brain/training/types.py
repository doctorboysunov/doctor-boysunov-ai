"""World-class Medical Brain training — canonical generated case schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.medical_brain.evaluation.blind_clinical.types import BlindTurn

TARGET_CASE_CAPACITY = 100_000
SEEDS_PER_SPECIALTY = 42
VARIANTS_PER_SEED = 104  # 23 × 42 × 104 = 100,464 unique cases

PRODUCTION_QUALITY = {
    "clinical_reasoning": 99.0,
    "safety": 95.0,
    "specialty_routing": 90.0,
    "red_flag_detection": 95.0,
    "reasoning_accuracy": 95.0,
    "overall": 92.0,
}

TRAINING_METRICS = (
    "reasoning_accuracy",
    "missed_diagnoses",
    "unnecessary_questions",
    "red_flag_detection",
    "specialty_routing",
    "patient_safety",
    "history_taking_quality",
    "differential_diagnosis",
    "final_recommendation",
)

# Phase 2.1 — standardized failure taxonomy
FAILURE_CATEGORIES = (
    "missed_diagnosis",
    "incorrect_differential_diagnosis",
    "delayed_red_flag_detection",
    "unnecessary_questions",
    "missing_important_history",
    "incorrect_specialty_routing",
    "incorrect_urgency",
    "unsafe_recommendation",
)


@dataclass(frozen=True)
class DiseaseSeed:
    """Blueprint for combinatorial case generation — one per disease presentation."""

    seed_id: str
    specialty: str
    category: str
    gold_diagnosis: str
    differential_diagnosis: tuple[str, ...]
    red_flags: tuple[str, ...]
    reasoning_steps: tuple[str, ...]
    expected_questions: tuple[str, ...]
    referral_decision: str
    urgency_level: str  # routine | urgent | emergency
    guideline_references: tuple[str, ...]
    opener_template: str
    followup_template: str
    assistant_probe: str
    expected_secondary: tuple[str, ...] = ()
    requires_emergency: bool = False
    lab_profile_key: str = "normal"
    imaging_profile_key: str = "none"
    ecg_profile_key: str = "none"


@dataclass
class CaseParameters:
    """Patient and clinical variation axes for unique case synthesis."""

    age: int
    sex: str  # male | female
    pregnancy_status: str  # none | pregnant | postpartum
    chronic_conditions: list[str]
    medications: list[str]
    occupation: str
    risk_factors: list[str]
    symptom_combination: list[str]
    disease_severity: str  # mild | moderate | severe | critical
    laboratory_values: dict[str, str]
    imaging_findings: dict[str, str]
    ecg_findings: str
    comorbidities: list[str]
    disease_progression: str  # acute | subacute | chronic | relapsing
    emergency_status: bool
    variant_index: int


@dataclass
class GeneratedClinicalCase:
    """Full generated case — patient-visible vs hidden ground truth."""

    id: str
    specialty: str
    category: str
    age_group: str
    # --- Patient-visible ---
    patient_profile: str
    turns: list[BlindTurn]
    parameters: CaseParameters
    # --- Hidden ground truth (never sent to engine) ---
    gold_diagnosis: str
    differential_diagnosis: list[str]
    red_flags: list[str]
    reasoning_steps: list[str]
    expected_questions: list[str]
    referral_decision: str
    urgency_level: str
    guideline_references: list[str]
    expected_primary: str
    expected_secondary: list[str]
    requires_emergency: bool = False

    @property
    def opening_message(self) -> str:
        for turn in self.turns:
            if turn.role == "user":
                return turn.content
        return self.turns[0].content if self.turns else ""

    @property
    def full_patient_text(self) -> str:
        return " ".join(t.content for t in self.turns if t.role == "user")

    def followup_snippet(self, max_len: int = 60) -> str:
        for turn in self.turns:
            if turn.role == "user" and turn.content != self.opening_message:
                return turn.content[:max_len]
        return self.opening_message[:max_len]

    def to_blind_case(self):
        """Convert to BlindCase for existing blind evaluation pipeline."""
        from app.medical_brain.evaluation.blind_clinical.types import BlindCase

        return BlindCase(
            id=self.id,
            category=self.category,
            age_group=self.age_group,
            patient_profile=self.patient_profile,
            turns=list(self.turns),
            expected_primary=self.expected_primary,
            expected_secondary=list(self.expected_secondary),
            expected_differentials=list(self.differential_diagnosis),
            expected_red_flags=list(self.red_flags),
            requires_emergency=self.requires_emergency,
            expected_recommendation=self.referral_decision,
            reasoning_rubric="; ".join(self.reasoning_steps[:3]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "specialty": self.specialty,
            "category": self.category,
            "age_group": self.age_group,
            "patient_profile": self.patient_profile,
            "turns": [{"role": t.role, "content": t.content} for t in self.turns],
            "parameters": {
                "age": self.parameters.age,
                "sex": self.parameters.sex,
                "pregnancy_status": self.parameters.pregnancy_status,
                "chronic_conditions": self.parameters.chronic_conditions,
                "medications": self.parameters.medications,
                "occupation": self.parameters.occupation,
                "risk_factors": self.parameters.risk_factors,
                "disease_severity": self.parameters.disease_severity,
                "laboratory_values": self.parameters.laboratory_values,
                "imaging_findings": self.parameters.imaging_findings,
                "ecg_findings": self.parameters.ecg_findings,
                "comorbidities": self.parameters.comorbidities,
                "disease_progression": self.parameters.disease_progression,
                "emergency_status": self.parameters.emergency_status,
            },
            "gold_diagnosis": self.gold_diagnosis,
            "differential_diagnosis": self.differential_diagnosis,
            "red_flags": self.red_flags,
            "reasoning_steps": self.reasoning_steps,
            "expected_questions": self.expected_questions,
            "referral_decision": self.referral_decision,
            "urgency_level": self.urgency_level,
            "guideline_references": self.guideline_references,
            "expected_primary": self.expected_primary,
            "expected_secondary": self.expected_secondary,
            "requires_emergency": self.requires_emergency,
        }


@dataclass
class TrainingScores:
    reasoning_accuracy: float = 0.0
    missed_diagnoses: float = 0.0  # inverted — higher is better
    unnecessary_questions: float = 0.0
    red_flag_detection: float = 0.0
    specialty_routing: float = 0.0
    patient_safety: float = 0.0
    history_taking_quality: float = 0.0
    differential_diagnosis: float = 0.0
    final_recommendation: float = 0.0

    @property
    def overall(self) -> float:
        values = [getattr(self, m) for m in TRAINING_METRICS]
        return round(sum(values) / len(values), 2)

    def to_dict(self) -> dict[str, float]:
        d = {m: getattr(self, m) for m in TRAINING_METRICS}
        d["overall"] = self.overall
        return d


@dataclass
class TrainingCaseResult:
    case_id: str
    specialty: str
    category: str
    passed: bool
    scores: TrainingScores
    routing_primary: str
    routing_secondary: list[str]
    missed_red_flags: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)
    improvement_actions: list[str] = field(default_factory=list)
    failure_categories: list[str] = field(default_factory=list)
    root_causes: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    question_count: int = 1
    expected_urgency: str = "routine"
    is_emergency_routed: bool = False
    evidence_agreement: float = 0.0
    evidence_passed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "specialty": self.specialty,
            "category": self.category,
            "passed": self.passed,
            "scores": self.scores.to_dict(),
            "routing_primary": self.routing_primary,
            "routing_secondary": self.routing_secondary,
            "missed_red_flags": self.missed_red_flags,
            "failure_reasons": self.failure_reasons,
            "improvement_actions": self.improvement_actions,
            "failure_categories": self.failure_categories,
            "root_causes": self.root_causes,
            "checks": self.checks,
            "question_count": self.question_count,
            "expected_urgency": self.expected_urgency,
            "is_emergency_routed": self.is_emergency_routed,
            "evidence_agreement": self.evidence_agreement,
            "evidence_passed": self.evidence_passed,
        }


@dataclass
class TrainingReport:
    timestamp: str = ""
    total_cases: int = 0
    evaluated: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    metric_averages: TrainingScores = field(default_factory=TrainingScores)
    by_specialty: dict[str, dict[str, float]] = field(default_factory=dict)
    recurring_failures: list[tuple[str, int]] = field(default_factory=list)
    optimization_patches: list[dict[str, str]] = field(default_factory=list)
    production_ready: bool = False
    requires_improvement: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_cases": self.total_cases,
            "evaluated": self.evaluated,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "metric_averages": self.metric_averages.to_dict(),
            "by_specialty": self.by_specialty,
            "recurring_failures": self.recurring_failures,
            "optimization_patches": self.optimization_patches,
            "production_ready": self.production_ready,
            "requires_improvement": self.requires_improvement,
        }


@dataclass
class FailedCaseRecord:
    """Persisted failure — case snapshot + analysis for continuous learning."""

    case_id: str
    cycle_id: int
    timestamp: str
    specialty: str
    category: str
    gold_diagnosis: str
    failure_categories: list[str]
    root_causes: list[str]
    failure_reasons: list[str]
    improvement_suggestions: list[str]
    scores: dict[str, float]
    routing_primary: str
    routing_secondary: list[str]
    missed_red_flags: list[str]
    case_snapshot: dict[str, Any]
    retry_count: int = 0
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "specialty": self.specialty,
            "category": self.category,
            "gold_diagnosis": self.gold_diagnosis,
            "failure_categories": self.failure_categories,
            "root_causes": self.root_causes,
            "failure_reasons": self.failure_reasons,
            "improvement_suggestions": self.improvement_suggestions,
            "scores": self.scores,
            "routing_primary": self.routing_primary,
            "routing_secondary": self.routing_secondary,
            "missed_red_flags": self.missed_red_flags,
            "case_snapshot": self.case_snapshot,
            "retry_count": self.retry_count,
            "resolved": self.resolved,
        }


@dataclass
class LearningCycleRecord:
    """One optimization cycle — metrics + delta from prior cycle."""

    cycle_id: int
    timestamp: str
    evaluated: int
    passed: int
    failed: int
    pass_rate: float
    metrics: dict[str, float]
    avg_questions: float
    by_specialty: dict[str, dict[str, float]]
    top_mistakes: list[tuple[str, int]]
    patches_applied: list[str]
    recurring_failures: list[str]
    safety_delta: float = 0.0
    optimization_complete: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "evaluated": self.evaluated,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "metrics": self.metrics,
            "avg_questions": self.avg_questions,
            "by_specialty": self.by_specialty,
            "top_mistakes": self.top_mistakes,
            "patches_applied": self.patches_applied,
            "recurring_failures": self.recurring_failures,
            "safety_delta": self.safety_delta,
            "optimization_complete": self.optimization_complete,
        }


@dataclass
class ClinicalQualityDashboard:
    """Latest dashboard snapshot with historical trend."""

    timestamp: str = ""
    cycle_id: int = 0
    reasoning_accuracy: float = 0.0
    differential_diagnosis_accuracy: float = 0.0
    red_flag_detection_rate: float = 0.0
    specialty_routing_accuracy: float = 0.0
    safety_score: float = 0.0
    avg_questions: float = 1.0
    pass_rate: float = 0.0
    pass_rate_by_specialty: dict[str, float] = field(default_factory=dict)
    top_recurring_mistakes: list[tuple[str, int]] = field(default_factory=list)
    improvement_trend: list[dict[str, Any]] = field(default_factory=list)
    optimization_complete: bool = False
    evidence_pass_rate: float = 0.0
    avg_evidence_agreement: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cycle_id": self.cycle_id,
            "reasoning_accuracy": self.reasoning_accuracy,
            "differential_diagnosis_accuracy": self.differential_diagnosis_accuracy,
            "red_flag_detection_rate": self.red_flag_detection_rate,
            "specialty_routing_accuracy": self.specialty_routing_accuracy,
            "safety_score": self.safety_score,
            "avg_questions": self.avg_questions,
            "pass_rate": self.pass_rate,
            "pass_rate_by_specialty": self.pass_rate_by_specialty,
            "top_recurring_mistakes": self.top_recurring_mistakes,
            "improvement_trend": self.improvement_trend,
            "optimization_complete": self.optimization_complete,
            "evidence_pass_rate": self.evidence_pass_rate,
            "avg_evidence_agreement": self.avg_evidence_agreement,
        }

"""Evidence-based clinical validation — internal types (never patient-facing)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ConfidenceLevel = Literal["high", "medium", "low"]

EVIDENCE_SOURCES = (
    "WHO",
    "NICE",
    "AHA/ACC",
    "ESC",
    "ADA",
    "KDIGO",
    "GOLD",
    "GINA",
    "IDSA",
    "ACOG",
    "AAN",
    "RCOG",
    "ATS",
    "AAP",
    "ASH",
    "EULAR",
    "ACR",
    "NCCN",
    "AUA",
    "AAO",
    "ACEP",
    "Surviving Sepsis",
    "Other",
)


@dataclass(frozen=True)
class GuidelineRule:
    """Single evidence rule derived from published guidance."""

    rule_id: str
    source: str
    source_id: str
    title: str
    criteria: tuple[str, ...]
    red_flags: tuple[str, ...] = ()
    required_actions: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()
    specialties: tuple[str, ...] = ()
    match_patterns: tuple[str, ...] = ()  # regex or keyword triggers


@dataclass
class EvidenceReport:
    """Internal evidence validation report — never shown to patients."""

    case_id: str
    gold_diagnosis: str
    sources_checked: list[str] = field(default_factory=list)
    agreement_score: float = 0.0
    conflicting_recommendations: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    confidence_level: ConfidenceLevel = "medium"
    missed_red_flags: list[str] = field(default_factory=list)
    unnecessary_investigations: list[str] = field(default_factory=list)
    unsafe_advice_risks: list[str] = field(default_factory=list)
    guideline_deviations: list[str] = field(default_factory=list)
    criteria_met: list[str] = field(default_factory=list)
    criteria_total: int = 0
    passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "gold_diagnosis": self.gold_diagnosis,
            "sources_checked": self.sources_checked,
            "agreement_score": self.agreement_score,
            "conflicting_recommendations": self.conflicting_recommendations,
            "missing_evidence": self.missing_evidence,
            "confidence_level": self.confidence_level,
            "missed_red_flags": self.missed_red_flags,
            "unnecessary_investigations": self.unnecessary_investigations,
            "unsafe_advice_risks": self.unsafe_advice_risks,
            "guideline_deviations": self.guideline_deviations,
            "criteria_met": self.criteria_met,
            "criteria_total": self.criteria_total,
            "passed": self.passed,
        }


@dataclass
class GuidelineDisagreement:
    """Logged disagreement for continuous improvement."""

    case_id: str
    timestamp: str
    source: str
    rule_id: str
    disagreement_type: str  # missed_red_flag | unnecessary_investigation | unsafe_advice | deviation | conflict
    description: str
    gold_diagnosis: str
    specialty: str
    severity: str  # low | medium | high

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "rule_id": self.rule_id,
            "disagreement_type": self.disagreement_type,
            "description": self.description,
            "gold_diagnosis": self.gold_diagnosis,
            "specialty": self.specialty,
            "severity": self.severity,
        }

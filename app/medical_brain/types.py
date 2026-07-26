"""Universal Medical Brain domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.clinical_brain.types import ClinicalBrainInternal, DoctorEmrUpdate, RankedHypothesis
from app.domain.consultation import ComplaintCategory
from app.domain.medical import MedicalSpecialty


@dataclass
class MedicalBrainInternal(ClinicalBrainInternal):
    """Extended internal reasoning with specialty routing and physician object."""

    primary_specialty: str = ""
    secondary_specialties: list[str] = field(default_factory=list)
    specialty_confidence: str = "low"
    coordination_notes: str = ""
    story_synthesis: str = ""
    step3_must_not_miss: list[RankedHypothesis] = field(default_factory=list)
    step3_alternatives: list[RankedHypothesis] = field(default_factory=list)
    ranked_differential: list[RankedHypothesis] = field(default_factory=list)
    contradictions_to_clarify: list[str] = field(default_factory=list)
    new_symptoms_this_turn: list[str] = field(default_factory=list)
    emergency_probability: float = 0.0
    recommended_urgency: str = "routine"
    evidence_validation: dict[str, Any] = field(default_factory=dict)
    clinical_confidence_score: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MedicalBrainInternal:
        base = ClinicalBrainInternal.from_dict(data)
        must_miss_raw = (data or {}).get("step3_must_not_miss") or []
        alt_raw = (data or {}).get("step3_alternatives") or []
        ranked_raw = (data or {}).get("ranked_differential") or []
        return cls(
            step1_patient_meaning=base.step1_patient_meaning,
            step2_memory_summary=base.step2_memory_summary,
            step3_hypotheses=base.step3_hypotheses,
            step4_red_flags=base.step4_red_flags,
            step4_emergency_assessment=base.step4_emergency_assessment,
            step5_missing_information=base.step5_missing_information,
            step6_next_question_topic=base.step6_next_question_topic,
            step6_next_question_rationale=base.step6_next_question_rationale,
            step6_interview_phase=base.step6_interview_phase,
            step6_alternatives_rejected=base.step6_alternatives_rejected,
            step6_clinical_confidence=base.step6_clinical_confidence,
            step7_stop_asking=base.step7_stop_asking,
            step7_ready_for_summary=base.step7_ready_for_summary,
            primary_specialty=str(data.get("primary_specialty") or "") if data else "",
            secondary_specialties=[str(x) for x in (data.get("secondary_specialties") or []) if str(x).strip()] if data else [],
            specialty_confidence=str(data.get("specialty_confidence") or "low") if data else "low",
            coordination_notes=str(data.get("coordination_notes") or "") if data else "",
            story_synthesis=str(data.get("story_synthesis") or "") if data else "",
            step3_must_not_miss=[RankedHypothesis.from_dict(x) for x in must_miss_raw if x],
            step3_alternatives=[RankedHypothesis.from_dict(x) for x in alt_raw if x],
            ranked_differential=[RankedHypothesis.from_dict(x) for x in ranked_raw if x],
            contradictions_to_clarify=[str(x) for x in ((data or {}).get("contradictions_to_clarify") or []) if str(x).strip()],
            new_symptoms_this_turn=[str(x) for x in ((data or {}).get("new_symptoms_this_turn") or []) if str(x).strip()],
            emergency_probability=float((data or {}).get("emergency_probability") or 0),
            recommended_urgency=str((data or {}).get("recommended_urgency") or "") if data else "routine",
            evidence_validation=dict((data or {}).get("evidence_validation") or {}),
            clinical_confidence_score=float((data or {}).get("clinical_confidence_score") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "primary_specialty": self.primary_specialty,
                "secondary_specialties": self.secondary_specialties,
                "specialty_confidence": self.specialty_confidence,
                "coordination_notes": self.coordination_notes,
                "story_synthesis": self.story_synthesis,
                "step3_must_not_miss": [
                    {"name": h.name, "probability": h.probability, "probability_pct": h.probability_pct, "rationale": h.rationale}
                    for h in self.step3_must_not_miss
                ],
                "step3_alternatives": [
                    {"name": h.name, "probability": h.probability, "probability_pct": h.probability_pct, "rationale": h.rationale}
                    for h in self.step3_alternatives
                ],
                "ranked_differential": [
                    {"name": h.name, "probability": h.probability, "probability_pct": h.probability_pct, "rationale": h.rationale}
                    for h in self.ranked_differential
                ],
                "contradictions_to_clarify": self.contradictions_to_clarify,
                "new_symptoms_this_turn": self.new_symptoms_this_turn,
                "emergency_probability": self.emergency_probability,
                "recommended_urgency": self.recommended_urgency,
                "evidence_validation": self.evidence_validation,
                "clinical_confidence_score": self.clinical_confidence_score,
            }
        )
        return result

    def format_emr_reasoning(self) -> str:
        lines = [super().format_emr_reasoning().replace("Clinical Brain", "Medical Brain")]
        if self.ranked_differential:
            ranked = "; ".join(f"{h.name} ({h.probability_pct}%)" for h in self.ranked_differential[:6])
            lines.append(f"Differensial (ranked): {ranked}")
        if self.story_synthesis:
            lines.append(f"Hikoya: {self.story_synthesis[:300]}")
        if self.step3_must_not_miss:
            ranked = "; ".join(f"{h.name}" for h in self.step3_must_not_miss[:4])
            lines.append(f"Ajratib o'tilmasin: {ranked}")
        if self.emergency_probability:
            lines.append(f"Favqulodda ehtimollik: {self.emergency_probability}")
        if self.clinical_confidence_score:
            lines.append(f"Klinik ishonch: {self.clinical_confidence_score}")
        if self.evidence_validation:
            ev = self.evidence_validation
            lines.append(
                f"Guideline agreement: {ev.get('agreement_score', '—')}% "
                f"({ev.get('confidence_level', '—')})"
            )
        if self.primary_specialty:
            specs = [self.primary_specialty, *self.secondary_specialties]
            lines.append(f"Mutaxassisliklar: {' + '.join(specs)}")
        if self.recommended_urgency:
            lines.append(f"Tavsiya shoshilinchlik: {self.recommended_urgency}")
        if self.coordination_notes:
            lines.append(f"Koordinatsiya: {self.coordination_notes}")
        return "\n".join(lines)

    @property
    def possible_causes(self) -> list[str]:
        return [h.name for h in self.step3_hypotheses if h.name]


@dataclass
class MedicalBrainInput:
    patient_id: int
    user_message: str
    primary_specialty: MedicalSpecialty
    secondary_specialties: list[MedicalSpecialty] = field(default_factory=list)
    complaint_category: ComplaintCategory = "other_neurological"
    session_messages: list[dict[str, str]] = field(default_factory=list)
    known_facts: dict[str, Any] = field(default_factory=dict)
    topics_covered: list[str] = field(default_factory=list)
    prior_complaints: list[str] = field(default_factory=list)
    visit_history: dict[str, Any] | None = None
    specialty_confidence: str = "low"
    is_emergency: bool = False


@dataclass
class MedicalBrainOutput:
    patient_reply: str = ""
    ready_for_help_menu: bool = False
    brief_summary_for_patient: str = ""
    known_facts: dict[str, Any] = field(default_factory=dict)
    topics_covered: list[str] = field(default_factory=list)
    doctor_emr: DoctorEmrUpdate = field(default_factory=DoctorEmrUpdate)
    internal: MedicalBrainInternal = field(default_factory=MedicalBrainInternal)
    primary_specialty: MedicalSpecialty = "internal_medicine"
    secondary_specialties: list[MedicalSpecialty] = field(default_factory=list)

    @property
    def suggests_emergency(self) -> bool:
        assessment = (self.internal.step4_emergency_assessment or "").lower()
        return assessment in {"emergency", "urgent", "shoshilinch", "103"} or bool(
            self.internal.step4_red_flags
            and assessment not in {"none", "routine", ""}
        )

"""Clinical Brain domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.consultation import ComplaintCategory


@dataclass
class RankedHypothesis:
    name: str
    probability: str = "medium"
    rationale: str = ""
    probability_pct: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | str) -> RankedHypothesis:
        if isinstance(data, str):
            return cls(name=data)
        raw_pct = data.get("probability_pct") or data.get("probability_value")
        pct = 0.0
        if raw_pct is not None:
            try:
                val = float(raw_pct)
                pct = val * 100 if val <= 1.0 else val
            except (TypeError, ValueError):
                pct = 0.0
        prob = str(data.get("probability") or "medium")
        if pct <= 0:
            try:
                val = float(prob)
                pct = val * 100 if val <= 1.0 else val
            except (TypeError, ValueError):
                pct = 0.0
        return cls(
            name=str(data.get("name") or data.get("diagnosis") or ""),
            probability=prob if prob in {"high", "medium", "low"} else ("high" if pct >= 30 else "medium" if pct >= 12 else "low"),
            rationale=str(data.get("rationale") or ""),
            probability_pct=round(pct, 1),
        )


@dataclass
class DoctorEmrUpdate:
    chief_complaint: str = ""
    history: str = ""
    timeline: str = ""
    clinical_notes: str = ""
    differential_diagnoses: list[str] = field(default_factory=list)
    recommended_investigations: list[str] = field(default_factory=list)
    urgency: str = "routine"
    risk_factors: list[str] = field(default_factory=list)
    red_flags_noted: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DoctorEmrUpdate:
        if not data:
            return cls()
        return cls(
            chief_complaint=str(data.get("chief_complaint") or ""),
            history=str(data.get("history") or ""),
            timeline=str(data.get("timeline") or ""),
            clinical_notes=str(data.get("clinical_notes") or ""),
            differential_diagnoses=list(data.get("differential_diagnoses") or []),
            recommended_investigations=list(data.get("recommended_investigations") or []),
            urgency=str(data.get("urgency") or "routine"),
            risk_factors=list(data.get("risk_factors") or []),
            red_flags_noted=list(data.get("red_flags_noted") or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "chief_complaint": self.chief_complaint,
            "history": self.history,
            "timeline": self.timeline,
            "clinical_notes": self.clinical_notes,
            "differential_diagnoses": self.differential_diagnoses,
            "recommended_investigations": self.recommended_investigations,
            "urgency": self.urgency,
            "risk_factors": self.risk_factors,
            "red_flags_noted": self.red_flags_noted,
        }

    def format_emr_block(self, internal: ClinicalBrainInternal | None = None) -> str:
        lines = [
            "--- Shifokor EMR (bemorga ko'rinmaydi) ---",
            f"Asosiy shikoyat: {self.chief_complaint}",
            f"Anamnez: {self.history}",
            f"Vaqt: {self.timeline}",
            f"Klinik eslatmalar: {self.clinical_notes}",
        ]
        if self.risk_factors:
            lines.append(f"Xavf omillari: {', '.join(self.risk_factors)}")
        if self.red_flags_noted:
            lines.append(f"Qizil bayroqlar: {', '.join(self.red_flags_noted)}")
        if self.differential_diagnoses:
            lines.append(f"Differensial tashxis: {'; '.join(self.differential_diagnoses)}")
        if self.recommended_investigations:
            lines.append(f"Tavsiya etilgan tekshiruvlar: {'; '.join(self.recommended_investigations)}")
        lines.append(f"Shoshilinchlik: {self.urgency}")
        if internal is not None:
            lines.append("")
            lines.append(internal.format_emr_reasoning())
        return "\n".join(lines)


@dataclass
class ClinicalBrainInternal:
    """7-step pipeline output — never shown to patient."""

    step1_patient_meaning: str = ""
    step2_memory_summary: str = ""
    step3_hypotheses: list[RankedHypothesis] = field(default_factory=list)
    step4_red_flags: list[str] = field(default_factory=list)
    step4_emergency_assessment: str = "none"
    step5_missing_information: list[str] = field(default_factory=list)
    step6_next_question_topic: str = ""
    step6_next_question_rationale: str = ""
    step6_interview_phase: str = ""
    step6_alternatives_rejected: list[str] = field(default_factory=list)
    step6_clinical_confidence: str = "low"
    step7_stop_asking: bool = False
    step7_ready_for_summary: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ClinicalBrainInternal:
        if not data:
            return cls()
        hypotheses_raw = data.get("step3_hypotheses") or data.get("hypotheses") or []
        hypotheses = [RankedHypothesis.from_dict(item) for item in hypotheses_raw if item]
        return cls(
            step1_patient_meaning=str(data.get("step1_patient_meaning") or data.get("patient_meaning") or ""),
            step2_memory_summary=str(data.get("step2_memory_summary") or data.get("memory_summary") or ""),
            step3_hypotheses=[h for h in hypotheses if h.name],
            step4_red_flags=[str(x) for x in (data.get("step4_red_flags") or data.get("red_flags") or []) if str(x).strip()],
            step4_emergency_assessment=str(
                data.get("step4_emergency_assessment") or data.get("emergency_assessment") or "none"
            ),
            step5_missing_information=[
                str(x) for x in (data.get("step5_missing_information") or data.get("missing_information") or []) if str(x).strip()
            ],
            step6_next_question_topic=str(data.get("step6_next_question_topic") or data.get("next_question_topic") or ""),
            step6_next_question_rationale=str(
                data.get("step6_next_question_rationale") or data.get("next_question_rationale") or ""
            ),
            step6_interview_phase=str(data.get("step6_interview_phase") or data.get("interview_phase") or ""),
            step6_alternatives_rejected=[
                str(x)
                for x in (data.get("step6_alternatives_rejected") or data.get("alternatives_rejected") or [])
                if str(x).strip()
            ],
            step6_clinical_confidence=str(data.get("step6_clinical_confidence") or data.get("clinical_confidence") or "low"),
            step7_stop_asking=bool(data.get("step7_stop_asking") or data.get("stop_asking")),
            step7_ready_for_summary=bool(data.get("step7_ready_for_summary") or data.get("ready_for_summary")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step1_patient_meaning": self.step1_patient_meaning,
            "step2_memory_summary": self.step2_memory_summary,
            "step3_hypotheses": [
                {"name": h.name, "probability": h.probability, "rationale": h.rationale, "probability_pct": h.probability_pct}
                for h in self.step3_hypotheses
            ],
            "step4_red_flags": self.step4_red_flags,
            "step4_emergency_assessment": self.step4_emergency_assessment,
            "step5_missing_information": self.step5_missing_information,
            "step6_next_question_topic": self.step6_next_question_topic,
            "step6_next_question_rationale": self.step6_next_question_rationale,
            "step6_interview_phase": self.step6_interview_phase,
            "step6_alternatives_rejected": self.step6_alternatives_rejected,
            "step6_clinical_confidence": self.step6_clinical_confidence,
            "step7_stop_asking": self.step7_stop_asking,
            "step7_ready_for_summary": self.step7_ready_for_summary,
        }

    def format_emr_reasoning(self) -> str:
        lines = ["--- Clinical Brain (ichki mulohaza) ---"]
        if self.step1_patient_meaning:
            lines.append(f"1. Bemor ma'nosi: {self.step1_patient_meaning}")
        if self.step2_memory_summary:
            lines.append(f"2. Xotira: {self.step2_memory_summary}")
        if self.step3_hypotheses:
            ranked = "; ".join(
                f"{h.name} ({h.probability_pct or h.probability}%)" if h.probability_pct else f"{h.name} ({h.probability})"
                for h in self.step3_hypotheses[:5]
            )
            lines.append(f"3. Gipotezalar: {ranked}")
        if self.step4_red_flags:
            lines.append(f"4. Qizil bayroqlar: {', '.join(self.step4_red_flags)}")
        if self.step5_missing_information:
            lines.append(f"5. Yetishmaydi: {'; '.join(self.step5_missing_information)}")
        if self.step6_next_question_rationale:
            lines.append(f"6. Keyingi savol ({self.step6_interview_phase}): {self.step6_next_question_rationale}")
        if self.step6_alternatives_rejected:
            lines.append(f"6. Rad etilgan: {'; '.join(self.step6_alternatives_rejected[:2])}")
        lines.append(f"4/6. Favqulodda: {self.step4_emergency_assessment}")
        lines.append(f"6. Ishonch: {self.step6_clinical_confidence}")
        return "\n".join(lines)

    @property
    def what_i_know(self) -> list[str]:
        items: list[str] = []
        if self.step1_patient_meaning:
            items.append(self.step1_patient_meaning)
        if self.step2_memory_summary:
            items.append(self.step2_memory_summary)
        return items

    @property
    def possible_neurological_causes(self) -> list[str]:
        return [h.name for h in self.step3_hypotheses if h.name]


@dataclass
class ClinicalBrainInput:
    patient_id: int
    user_message: str
    complaint_category: ComplaintCategory
    session_messages: list[dict[str, str]] = field(default_factory=list)
    known_facts: dict[str, Any] = field(default_factory=dict)
    topics_covered: list[str] = field(default_factory=list)
    prior_complaints: list[str] = field(default_factory=list)
    visit_history: dict[str, Any] | None = None
    conversation_snippet: list[dict[str, str]] | None = None


@dataclass
class ClinicalBrainOutput:
    patient_reply: str = ""
    ready_for_help_menu: bool = False
    brief_summary_for_patient: str = ""
    known_facts: dict[str, Any] = field(default_factory=dict)
    topics_covered: list[str] = field(default_factory=list)
    doctor_emr: DoctorEmrUpdate = field(default_factory=DoctorEmrUpdate)
    internal: ClinicalBrainInternal = field(default_factory=ClinicalBrainInternal)

    @property
    def suggests_emergency(self) -> bool:
        assessment = (self.internal.step4_emergency_assessment or "").lower()
        return assessment in {"emergency", "urgent", "shoshilinch", "103"} or bool(
            self.internal.step4_red_flags
            and assessment not in {"none", "routine", ""}
        )

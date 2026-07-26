"""Professional medical consultation engine — domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ComplaintCategory = Literal[
    "headache",
    "low_back_pain",
    "neck_pain",
    "vertigo",
    "stroke",
    "neuropathy",
    "facial_nerve_palsy",
    "tremor",
    "memory_problems",
    "sleep_disorders",
    "anxiety",
    "depression",
    "other_neurological",
]

ConsultationPhase = Literal[
    "collecting",
    "awaiting_help_choice",
    "awaiting_session_choice",
    "awaiting_complaint_clarification",
    "complete",
    "emergency",
]

COMPLAINT_LABELS: dict[str, str] = {
    "headache": "Bosh og'rig'i",
    "low_back_pain": "Bel og'rig'i",
    "neck_pain": "Bo'yin og'rig'i",
    "vertigo": "Bosh aylanishi",
    "stroke": "Insult / falaj belgilari",
    "neuropathy": "Neuropatiya / nerv kasalligi",
    "facial_nerve_palsy": "Yuz nervi falaji",
    "tremor": "Titroq",
    "memory_problems": "Xotira muammolari",
    "sleep_disorders": "Uyqu buzilishi",
    "anxiety": "Xavotir / tashvish",
    "depression": "Depressiya",
    "other_neurological": "Boshqa nevrologik shikoyat",
}

URGENCY_LEVELS = ("routine", "urgent", "emergency")


@dataclass(frozen=True)
class ConsultationQuestion:
    id: str
    text: str
    required: bool = True
    order: int = 0
    red_flag_patterns: tuple[str, ...] = ()
    red_flag_label: str | None = None


@dataclass
class ConsultationSummary:
    chief_complaint: str
    history: str
    timeline: str
    risk_factors: list[str]
    red_flags: list[str]
    possible_differential_diagnoses: list[str]
    recommended_investigations: list[str]
    urgency: str
    recommended_visit_type: str
    follow_up_plan: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chief_complaint": self.chief_complaint,
            "history": self.history,
            "timeline": self.timeline,
            "risk_factors": self.risk_factors,
            "red_flags": self.red_flags,
            "possible_differential_diagnoses": self.possible_differential_diagnoses,
            "recommended_investigations": self.recommended_investigations,
            "urgency": self.urgency,
            "recommended_visit_type": self.recommended_visit_type,
            "follow_up_plan": self.follow_up_plan,
        }

    def format_text(self) -> str:
        lines = [
            "📋 **Tibbiy konsultatsiya xulosasi**",
            "",
            f"**Asosiy shikoyat:** {self.chief_complaint}",
            f"**Anamnez:** {self.history}",
            f"**Vaqt chizig'i:** {self.timeline}",
        ]
        if self.risk_factors:
            lines.append(f"**Xavf omillari:** {', '.join(self.risk_factors)}")
        if self.red_flags:
            lines.append(f"**Qizil bayroqlar:** {', '.join(self.red_flags)}")
        if self.possible_differential_diagnoses:
            lines.append(
                "**Ehtimoliy differensial tashxislar:** "
                + "; ".join(self.possible_differential_diagnoses)
            )
        if self.recommended_investigations:
            lines.append(
                "**Tavsiya etilgan tekshiruvlar:** "
                + "; ".join(self.recommended_investigations)
            )
        lines.extend(
            [
                f"**Shoshilinchlik:** {self.urgency}",
                f"**Tavsiya etilgan qabul turi:** {self.recommended_visit_type}",
                f"**Keyingi reja:** {self.follow_up_plan}",
            ]
        )
        return "\n".join(lines)


@dataclass
class ConsultationSession:
    id: int
    patient_id: int
    visit_id: int
    complaint_category: ComplaintCategory
    phase: ConsultationPhase
    asked_question_ids: list[str] = field(default_factory=list)
    answers: dict[str, str] = field(default_factory=dict)
    current_question_id: str | None = None
    summary: dict[str, Any] | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ConsultationSession:
        import json

        asked = json.loads(row.get("asked_question_ids") or "[]")
        answers = json.loads(row.get("answers_json") or "{}")
        summary_raw = row.get("summary_json")
        summary = json.loads(summary_raw) if summary_raw else None
        return cls(
            id=int(row["id"]),
            patient_id=int(row["patient_id"]),
            visit_id=int(row["visit_id"]),
            complaint_category=row["complaint_category"],
            phase=row["phase"],
            asked_question_ids=list(asked),
            answers=dict(answers),
            current_question_id=row.get("current_question_id"),
            summary=summary,
        )


@dataclass(frozen=True)
class ConsultationTurnResult:
    reply: str
    phase: ConsultationPhase
    session_id: int | None = None
    used_consultation_engine: bool = True
    emergency: bool = False
    completed: bool = False

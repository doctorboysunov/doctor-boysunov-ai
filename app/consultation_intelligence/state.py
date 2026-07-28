"""ConsultationState — single source of truth for an active consultation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

ENGINE_VERSION = "6.8.1"


class ConsultationStage(str, Enum):
    RECOGNIZING = "recognizing"
    COLLECTING = "collecting"
    CLOSURE = "closure"
    AWAITING_HELP = "awaiting_help"
    COMPLETE = "complete"
    EMERGENCY = "emergency"


class EmergencyStatus(str, Enum):
    NONE = "none"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"


@dataclass
class AskedQuestion:
    topic_slug: str
    question_text: str
    turn: int

    def to_dict(self) -> dict[str, Any]:
        return {"topic_slug": self.topic_slug, "question_text": self.question_text, "turn": self.turn}


@dataclass
class CollectedFact:
    topic_slug: str
    raw_answer: str
    parsed_value: str = ""
    turn: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_slug": self.topic_slug,
            "raw_answer": self.raw_answer,
            "parsed_value": self.parsed_value or self.raw_answer,
            "turn": self.turn,
        }


@dataclass
class ConsultationState:
    """Authoritative consultation memory — the only source of truth."""

    stage: ConsultationStage = ConsultationStage.RECOGNIZING
    pathway_id: str = ""
    syndrome_id: str = ""
    syndrome_label_uz: str = ""
    base_category: str = "low_back_pain"
    dominant_complaint: str = ""
    opening_complaint: str = ""
    recognition_rationale: str = ""
    pathway_locked: bool = False
    turn_count: int = 0

    pending_topic: str | None = None
    asked: list[AskedQuestion] = field(default_factory=list)
    answered_slugs: list[str] = field(default_factory=list)
    facts: list[CollectedFact] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)

    differential: list[dict[str, Any]] = field(default_factory=list)
    confirmed_red_flags: list[str] = field(default_factory=list)
    emergency_status: EmergencyStatus = EmergencyStatus.NONE
    emergency_suspect_flags: list[str] = field(default_factory=list)

    secondary_symptoms: list[dict[str, Any]] = field(default_factory=list)
    supplemental_questions: list[dict[str, Any]] = field(default_factory=list)

    clinical_assessment: dict[str, Any] = field(default_factory=dict)
    pending_clarification: dict[str, Any] | None = None

    completion_pct: float = 0.0
    ready_for_closure: bool = False
    help_menu_shown: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_version": ENGINE_VERSION,
            "stage": self.stage.value,
            "pathway_id": self.pathway_id,
            "syndrome_id": self.syndrome_id,
            "syndrome_label_uz": self.syndrome_label_uz,
            "base_category": self.base_category,
            "dominant_complaint": self.dominant_complaint,
            "opening_complaint": self.opening_complaint,
            "recognition_rationale": self.recognition_rationale,
            "pathway_locked": self.pathway_locked,
            "turn_count": self.turn_count,
            "pending_topic": self.pending_topic,
            "asked": [a.to_dict() for a in self.asked],
            "answered_slugs": list(self.answered_slugs),
            "facts": [f.to_dict() for f in self.facts],
            "missing_information": list(self.missing_information),
            "differential": list(self.differential),
            "confirmed_red_flags": list(self.confirmed_red_flags),
            "emergency_status": self.emergency_status.value,
            "emergency_suspect_flags": list(self.emergency_suspect_flags),
            "secondary_symptoms": list(self.secondary_symptoms),
            "supplemental_questions": list(self.supplemental_questions),
            "clinical_assessment": dict(self.clinical_assessment),
            "pending_clarification": self.pending_clarification,
            "completion_pct": self.completion_pct,
            "ready_for_closure": self.ready_for_closure,
            "help_menu_shown": self.help_menu_shown,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ConsultationState:
        if not data:
            return cls()
        try:
            stage = ConsultationStage(str(data.get("stage") or ConsultationStage.RECOGNIZING.value))
        except ValueError:
            stage = ConsultationStage.COLLECTING
        try:
            emergency = EmergencyStatus(str(data.get("emergency_status") or EmergencyStatus.NONE.value))
        except ValueError:
            emergency = EmergencyStatus.NONE

        asked_raw = data.get("asked") or []
        facts_raw = data.get("facts") or []
        return cls(
            stage=stage,
            pathway_id=str(data.get("pathway_id") or data.get("syndrome_id") or ""),
            syndrome_id=str(data.get("syndrome_id") or data.get("pathway_id") or ""),
            syndrome_label_uz=str(data.get("syndrome_label_uz") or ""),
            base_category=str(data.get("base_category") or "low_back_pain"),
            dominant_complaint=str(data.get("dominant_complaint") or ""),
            opening_complaint=str(data.get("opening_complaint") or ""),
            recognition_rationale=str(data.get("recognition_rationale") or ""),
            pathway_locked=bool(data.get("pathway_locked")),
            turn_count=int(data.get("turn_count") or 0),
            pending_topic=data.get("pending_topic") or None,
            asked=[
                AskedQuestion(
                    topic_slug=str(a.get("topic_slug") or ""),
                    question_text=str(a.get("question_text") or ""),
                    turn=int(a.get("turn") or 0),
                )
                for a in asked_raw
                if isinstance(a, dict)
            ],
            answered_slugs=[str(x) for x in (data.get("answered_slugs") or data.get("answered_topics") or []) if str(x).strip()],
            facts=[
                CollectedFact(
                    topic_slug=str(f.get("topic_slug") or ""),
                    raw_answer=str(f.get("raw_answer") or ""),
                    parsed_value=str(f.get("parsed_value") or ""),
                    turn=int(f.get("turn") or 0),
                )
                for f in facts_raw
                if isinstance(f, dict)
            ],
            missing_information=[str(x) for x in (data.get("missing_information") or data.get("missing_topics") or []) if str(x).strip()],
            differential=list(data.get("differential") or []),
            confirmed_red_flags=[str(x) for x in (data.get("confirmed_red_flags") or []) if str(x).strip()],
            emergency_status=emergency,
            emergency_suspect_flags=[str(x) for x in (data.get("emergency_suspect_flags") or []) if str(x).strip()],
            secondary_symptoms=[
                dict(s) for s in (data.get("secondary_symptoms") or []) if isinstance(s, dict)
            ],
            supplemental_questions=[
                dict(q) for q in (data.get("supplemental_questions") or []) if isinstance(q, dict)
            ],
            clinical_assessment=dict(data.get("clinical_assessment") or {}),
            pending_clarification=(
                dict(data["pending_clarification"])
                if isinstance(data.get("pending_clarification"), dict)
                else None
            ),
            completion_pct=float(data.get("completion_pct") or 0),
            ready_for_closure=bool(data.get("ready_for_closure")),
            help_menu_shown=bool(data.get("help_menu_shown")),
        )

    @classmethod
    def load(cls, answers: dict[str, Any]) -> ConsultationState:
        raw = answers.get("consultation_state")
        if isinstance(raw, dict):
            return cls.from_dict(raw)
        known = answers.get("known_facts") or {}
        if isinstance(known, dict) and known.get("consultation_state"):
            return cls.from_dict(known["consultation_state"])
        return cls.from_dict(known if isinstance(known, dict) else {})

    def persist_into(self, answers: dict[str, Any]) -> None:
        """Write state into session answers blob — sole authority."""
        answers["consultation_state"] = self.to_dict()
        known = dict(answers.get("known_facts") or {})
        known["consultation_state"] = self.to_dict()
        known["clinical_pathway_id"] = self.pathway_id
        known["neurological_syndrome"] = self.syndrome_label_uz
        known["syndrome_label_uz"] = self.syndrome_label_uz
        known["dominant_complaint"] = self.dominant_complaint
        known["engine_version"] = ENGINE_VERSION
        answers["known_facts"] = known
        answers["topics_covered"] = list(self.answered_slugs)
        answers["asked_question_ids"] = list(self.answered_slugs)

    def has_asked(self, topic_slug: str) -> bool:
        return topic_slug in self.answered_slugs or any(a.topic_slug == topic_slug for a in self.asked)

    def record_answer(self, topic_slug: str, raw_answer: str, parsed_value: str = "") -> None:
        if not topic_slug or topic_slug in self.answered_slugs:
            return
        self.answered_slugs.append(topic_slug)
        self.facts.append(
            CollectedFact(
                topic_slug=topic_slug,
                raw_answer=raw_answer.strip(),
                parsed_value=(parsed_value or raw_answer).strip(),
                turn=self.turn_count,
            )
        )
        if self.pending_topic == topic_slug:
            self.pending_topic = None

    def record_question(self, topic_slug: str, question_text: str) -> None:
        if topic_slug in self.answered_slugs:
            raise ValueError(f"Cannot re-ask answered topic: {topic_slug}")
        self.pending_topic = topic_slug
        self.asked.append(AskedQuestion(topic_slug=topic_slug, question_text=question_text, turn=self.turn_count))

    def fact_map(self) -> dict[str, str]:
        return {f.topic_slug: f.parsed_value or f.raw_answer for f in self.facts}

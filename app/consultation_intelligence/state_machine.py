"""Consultation intelligence — state machine and stage definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

ENGINE_VERSION = "5.0.0"


class ConsultationStage(str, Enum):
    RECOGNIZING = "recognizing"
    COLLECTING = "collecting"
    CLOSURE = "closure"
    AWAITING_HELP = "awaiting_help"
    COMPLETE = "complete"
    EMERGENCY = "emergency"


@dataclass
class ConsultationState:
    """Authoritative consultation memory — never restart, never duplicate questions."""

    stage: ConsultationStage = ConsultationStage.RECOGNIZING
    pathway_id: str = ""
    syndrome: str = ""
    syndrome_label_uz: str = ""
    dominant_complaint: str = ""
    recognition_rationale: str = ""
    answered_topics: list[str] = field(default_factory=list)
    pending_topic: str | None = None
    collected_answers: dict[str, str] = field(default_factory=dict)
    missing_topics: list[str] = field(default_factory=list)
    completion_pct: float = 0.0
    turn_count: int = 0
    pathway_locked: bool = False
    opening_complaint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_version": ENGINE_VERSION,
            "stage": self.stage.value,
            "pathway_id": self.pathway_id,
            "syndrome": self.syndrome,
            "syndrome_label_uz": self.syndrome_label_uz,
            "dominant_complaint": self.dominant_complaint,
            "recognition_rationale": self.recognition_rationale,
            "answered_topics": list(self.answered_topics),
            "pending_topic": self.pending_topic,
            "collected_answers": dict(self.collected_answers),
            "missing_topics": list(self.missing_topics),
            "completion_pct": self.completion_pct,
            "turn_count": self.turn_count,
            "pathway_locked": self.pathway_locked,
            "opening_complaint": self.opening_complaint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ConsultationState:
        if not data:
            return cls()
        stage_raw = str(data.get("stage") or ConsultationStage.RECOGNIZING.value)
        try:
            stage = ConsultationStage(stage_raw)
        except ValueError:
            stage = ConsultationStage.COLLECTING
        return cls(
            stage=stage,
            pathway_id=str(data.get("pathway_id") or ""),
            syndrome=str(data.get("syndrome") or ""),
            syndrome_label_uz=str(data.get("syndrome_label_uz") or ""),
            dominant_complaint=str(data.get("dominant_complaint") or ""),
            recognition_rationale=str(data.get("recognition_rationale") or ""),
            answered_topics=[str(x) for x in (data.get("answered_topics") or []) if str(x).strip()],
            pending_topic=data.get("pending_topic") or None,
            collected_answers={str(k): str(v) for k, v in (data.get("collected_answers") or {}).items()},
            missing_topics=[str(x) for x in (data.get("missing_topics") or []) if str(x).strip()],
            completion_pct=float(data.get("completion_pct") or 0),
            turn_count=int(data.get("turn_count") or 0),
            pathway_locked=bool(data.get("pathway_locked")),
            opening_complaint=str(data.get("opening_complaint") or ""),
        )

    @classmethod
    def load(cls, known_facts: dict[str, Any]) -> ConsultationState:
        raw = known_facts.get("consultation_state")
        if isinstance(raw, dict):
            return cls.from_dict(raw)
        legacy_topics = list(known_facts.get("answered_topics") or [])
        state = cls()
        if legacy_topics:
            state.answered_topics = legacy_topics
        state.pathway_id = str(known_facts.get("clinical_pathway_id") or "")
        state.syndrome = str(known_facts.get("neurological_syndrome") or "")
        return state

    def save_to(self, known_facts: dict[str, Any]) -> None:
        known_facts["consultation_state"] = self.to_dict()
        known_facts["clinical_pathway_id"] = self.pathway_id
        known_facts["neurological_syndrome"] = self.syndrome
        known_facts["syndrome_label_uz"] = self.syndrome_label_uz
        known_facts["dominant_complaint"] = self.dominant_complaint
        known_facts["pathway_completion_pct"] = self.completion_pct
        known_facts["answered_topics"] = list(self.answered_topics)
        known_facts["engine_version"] = ENGINE_VERSION

    def mark_answered(self, topic_slug: str, answer_text: str) -> None:
        if not topic_slug or topic_slug in self.answered_topics:
            return
        self.answered_topics.append(topic_slug)
        self.collected_answers[topic_slug] = answer_text.strip()
        if self.pending_topic == topic_slug:
            self.pending_topic = None

    def is_topic_answered(self, topic_slug: str) -> bool:
        return topic_slug in self.answered_topics

    def set_pending(self, topic_slug: str) -> None:
        if topic_slug in self.answered_topics:
            raise ValueError(f"Cannot ask already answered topic: {topic_slug}")
        self.pending_topic = topic_slug

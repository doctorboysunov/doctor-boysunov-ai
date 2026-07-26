"""Clinical pathway domain types — expandable registry architecture."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.domain.consultation import ComplaintCategory

PathwayPhase = Literal["triage", "narrative", "discriminator", "context", "closure"]
RecognitionConfidence = Literal["high", "medium", "low"]

PHASE_4_VERSION = "4.0.0"


@dataclass(frozen=True)
class PathwayNode:
    """One disease-specific question in a dynamic pathway."""

    id: str
    topic_slug: str
    phase: PathwayPhase
    question_focus: str
    question_uz: str = ""
    required: bool = True
    depends_on: tuple[str, ...] = ()
    rationale: str = ""
    clinical_info_label: str = ""

    @property
    def text(self) -> str:
        return self.question_uz or self.question_focus


@dataclass(frozen=True)
class ClinicalPathway:
    """Expandable neurological syndrome pathway definition."""

    id: str
    syndrome: str
    syndrome_label_uz: str
    base_category: ComplaintCategory
    description_uz: str
    recognition_keywords: tuple[str, ...] = ()
    recognition_patterns: tuple[str, ...] = ()
    priority: int = 50
    triage_must_not_miss: str = ""
    nodes: tuple[PathwayNode, ...] = ()
    differential_targets: tuple[str, ...] = ()
    min_required_topics: int = 4

    @property
    def required_topic_slugs(self) -> tuple[str, ...]:
        return tuple(n.topic_slug for n in self.nodes if n.required)


@dataclass
class PathwayContext:
    """Runtime state for one consultation turn."""

    pathway_id: str
    syndrome: str
    syndrome_label_uz: str
    base_category: ComplaintCategory
    recognition_confidence: RecognitionConfidence = "medium"
    recognition_rationale: str = ""
    current_node: PathwayNode | None = None
    completed_topics: list[str] = field(default_factory=list)
    pending_required_topics: list[str] = field(default_factory=list)
    completion_pct: float = 0.0
    ready_for_closure: bool = False
    total_required: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pathway_id": self.pathway_id,
            "syndrome": self.syndrome,
            "syndrome_label_uz": self.syndrome_label_uz,
            "base_category": self.base_category,
            "recognition_confidence": self.recognition_confidence,
            "recognition_rationale": self.recognition_rationale,
            "current_node_id": self.current_node.id if self.current_node else None,
            "current_topic_slug": self.current_node.topic_slug if self.current_node else None,
            "completed_topics": self.completed_topics,
            "pending_required_topics": self.pending_required_topics,
            "completion_pct": round(self.completion_pct, 1),
            "ready_for_closure": self.ready_for_closure,
            "total_required": self.total_required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PathwayContext | None:
        if not data or not data.get("pathway_id"):
            return None
        return cls(
            pathway_id=str(data.get("pathway_id") or ""),
            syndrome=str(data.get("syndrome") or ""),
            syndrome_label_uz=str(data.get("syndrome_label_uz") or ""),
            base_category=data.get("base_category") or "other_neurological",  # type: ignore[arg-type]
            recognition_confidence=data.get("recognition_confidence") or "medium",  # type: ignore[arg-type]
            recognition_rationale=str(data.get("recognition_rationale") or ""),
            completed_topics=[str(x) for x in (data.get("completed_topics") or []) if str(x).strip()],
            pending_required_topics=[str(x) for x in (data.get("pending_required_topics") or []) if str(x).strip()],
            completion_pct=float(data.get("completion_pct") or 0),
            ready_for_closure=bool(data.get("ready_for_closure")),
            total_required=int(data.get("total_required") or 0),
        )

"""ClinicalReasoner — syndrome recognition and differential diagnosis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.clinical_brain.clinical_pathways import get_pathway, recognize_pathway
from app.clinical_brain.senior_neurologist import identify_dominant_complaint
from app.consultation_intelligence.answer_parser import is_positive
from app.consultation_intelligence.emergency import evaluate_emergency_from_facts
from app.consultation_intelligence.state import ConsultationState, EmergencyStatus
from app.domain.consultation import ComplaintCategory


@dataclass(frozen=True)
class ReasoningSnapshot:
    pathway_id: str
    syndrome_label_uz: str
    base_category: ComplaintCategory
    dominant_complaint: str
    rationale: str
    differential: list[dict[str, Any]]
    missing_information: list[str]
    emergency_status: EmergencyStatus
    confirmed_red_flags: list[str]


def _build_differential(pathway_id: str, facts: dict[str, str]) -> list[dict[str, Any]]:
    pathway = get_pathway(pathway_id)
    if not pathway or not pathway.differential_targets:
        return [{"name": pathway.syndrome if pathway else pathway_id, "probability_pct": 40.0, "rank": 1}]

    ranked: list[dict[str, Any]] = []
    for i, name in enumerate(pathway.differential_targets[:5]):
        pct = max(12.0, 48.0 - i * 9)
        ranked.append({"name": name, "probability_pct": pct, "rank": i + 1})

    if facts:
        for slug, val in facts.items():
            val_lower = (val or "").lower()
            if "cauda" in slug and is_positive(val):
                if any(w in val_lower for w in ("ikki", "siydik", "najas", "hojat")):
                    for item in ranked:
                        if "cauda" in item["name"].lower():
                            item["probability_pct"] = min(95.0, item["probability_pct"] + 30)
            if "central" in slug and is_positive(val):
                if any(w in val_lower for w in ("nutq", "yuz", "qo'l", "insult", "birdan")):
                    for item in ranked:
                        if "insult" in item["name"].lower() or "markaziy" in item["name"].lower():
                            item["probability_pct"] = min(95.0, item["probability_pct"] + 25)

    ranked.sort(key=lambda x: x["probability_pct"], reverse=True)
    for i, item in enumerate(ranked):
        item["rank"] = i + 1
    return ranked


def _evaluate_emergency(state: ConsultationState, facts: dict[str, str]) -> tuple[EmergencyStatus, list[str]]:
    return evaluate_emergency_from_facts(state, facts)


class ClinicalReasoner:
    """Determine syndrome and update differential from consultation state."""

    def recognize(self, narrative: str, state: ConsultationState) -> ReasoningSnapshot:
        if state.pathway_locked and state.pathway_id:
            pathway = get_pathway(state.pathway_id)
            return self._snapshot_from_pathway(state, pathway, state.recognition_rationale or "Locked pathway.")

        dominant = identify_dominant_complaint(narrative, state.base_category or "low_back_pain")
        pathway_id, _conf, rationale = recognize_pathway(
            narrative,
            category_hint=dominant.dominant_category,
            known_facts={"clinical_pathway_id": state.pathway_id} if state.pathway_id else {},
        )
        pathway = get_pathway(pathway_id)
        if not pathway:
            pathway_id = "unclassified_neurology"
            pathway = get_pathway(pathway_id)

        state.pathway_id = pathway_id
        state.syndrome_id = pathway_id
        state.syndrome_label_uz = pathway.syndrome_label_uz if pathway else dominant.dominant_label
        state.base_category = pathway.base_category if pathway else dominant.dominant_category
        state.dominant_complaint = dominant.dominant_label
        state.recognition_rationale = rationale
        state.pathway_locked = True
        return self._snapshot_from_pathway(state, pathway, rationale)

    def update(self, state: ConsultationState) -> ReasoningSnapshot:
        pathway = get_pathway(state.pathway_id)
        facts = state.fact_map()
        state.differential = _build_differential(state.pathway_id, facts)
        emergency, confirmed = _evaluate_emergency(state, facts)
        state.emergency_status = emergency
        state.confirmed_red_flags = confirmed
        return self._snapshot_from_pathway(state, pathway, state.recognition_rationale)

    def _snapshot_from_pathway(
        self,
        state: ConsultationState,
        pathway: Any,
        rationale: str,
    ) -> ReasoningSnapshot:
        facts = state.fact_map()
        diff = state.differential or _build_differential(state.pathway_id, facts)
        state.differential = diff
        missing = state.missing_information
        return ReasoningSnapshot(
            pathway_id=state.pathway_id,
            syndrome_label_uz=state.syndrome_label_uz,
            base_category=state.base_category,  # type: ignore[arg-type]
            dominant_complaint=state.dominant_complaint,
            rationale=rationale,
            differential=diff,
            missing_information=missing,
            emergency_status=state.emergency_status,
            confirmed_red_flags=list(state.confirmed_red_flags),
        )

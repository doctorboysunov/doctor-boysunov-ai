"""ClinicalReasoner — syndrome recognition, differential, and clinical assessment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.clinical_brain.clinical_pathways import get_pathway, recognize_pathway
from app.clinical_brain.senior_neurologist import identify_dominant_complaint
from app.consultation_intelligence.contradiction_detector import detect_contradictions
from app.consultation_intelligence.differential_engine import (
    build_clinical_assessment,
    update_differential,
)
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
    clinical_assessment: dict[str, Any]


def _evaluate_emergency(state: ConsultationState, facts: dict[str, str]) -> tuple[EmergencyStatus, list[str]]:
    return evaluate_emergency_from_facts(state, facts)


class ClinicalReasoner:
    """
    Senior-neurologist reasoning loop:
    Complaint → Syndrome → Differential → Missing info → (via DecisionEngine) Best question.
    """

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

        state.differential = update_differential(state, facts)
        state.clinical_assessment = build_clinical_assessment(state, state.differential)

        emergency, confirmed = _evaluate_emergency(state, facts)
        state.emergency_status = emergency
        state.confirmed_red_flags = confirmed

        contradiction = detect_contradictions(state)
        if contradiction and contradiction.topic_slug not in state.answered_slugs:
            state.pending_clarification = {
                "code": contradiction.code,
                "topic_slug": contradiction.topic_slug,
                "question_text": contradiction.clarification_question,
            }
        elif state.pending_clarification and state.pending_clarification.get("topic_slug") in state.answered_slugs:
            state.pending_clarification = None

        return self._snapshot_from_pathway(state, pathway, state.recognition_rationale)

    def _snapshot_from_pathway(
        self,
        state: ConsultationState,
        pathway: Any,
        rationale: str,
    ) -> ReasoningSnapshot:
        facts = state.fact_map()
        if not state.differential:
            state.differential = update_differential(state, facts)
        if not state.clinical_assessment:
            state.clinical_assessment = build_clinical_assessment(state, state.differential)

        return ReasoningSnapshot(
            pathway_id=state.pathway_id,
            syndrome_label_uz=state.syndrome_label_uz,
            base_category=state.base_category,  # type: ignore[arg-type]
            dominant_complaint=state.dominant_complaint,
            rationale=rationale,
            differential=state.differential,
            missing_information=state.missing_information,
            emergency_status=state.emergency_status,
            confirmed_red_flags=list(state.confirmed_red_flags),
            clinical_assessment=dict(state.clinical_assessment),
        )

"""DecisionEngine — select the single best next clinical question."""

from __future__ import annotations

from dataclasses import dataclass

from app.clinical_brain.clinical_pathways import get_pathway
from app.clinical_brain.clinical_pathways.types import PathwayNode
from app.consultation_intelligence.state import ConsultationState, EmergencyStatus


@dataclass(frozen=True)
class ClinicalDecision:
    action: str  # ask | closure | emergency
    topic_slug: str = ""
    question_text: str = ""
    rationale: str = ""
    missing_information: list[str] | None = None


def _dependencies_met(node: PathwayNode, answered: set[str]) -> bool:
    return all(dep in answered for dep in node.depends_on)


def _select_next_node(pathway_id: str, answered: set[str]) -> PathwayNode | None:
    pathway = get_pathway(pathway_id)
    if not pathway:
        return None
    for node in pathway.nodes:
        if node.topic_slug in answered:
            continue
        if not _dependencies_met(node, answered):
            continue
        return node
    return None


def _pathway_progress(pathway_id: str, answered: set[str]) -> tuple[float, bool, list[str]]:
    pathway = get_pathway(pathway_id)
    if not pathway:
        return 0.0, False, []
    required = [n for n in pathway.nodes if n.required]
    completed = [n for n in required if n.topic_slug in answered]
    pending = [n.topic_slug for n in required if n.topic_slug not in answered]
    pct = len(completed) / max(len(required), 1) * 100.0
    triage_slugs = {n.topic_slug for n in pathway.nodes if n.phase == "triage"}
    triage_done = bool(triage_slugs & answered) or not triage_slugs
    ready = len(pending) == 0 and triage_done
    return pct, ready, pending


class DecisionEngine:
    """Choose exactly one next action based on state and reasoning."""

    def decide(self, state: ConsultationState) -> ClinicalDecision:
        if state.emergency_status == EmergencyStatus.CONFIRMED:
            return ClinicalDecision(
                action="emergency",
                rationale="Confirmed red flags require emergency evaluation.",
            )

        answered = set(state.answered_slugs)
        pct, ready, pending = _pathway_progress(state.pathway_id, answered)
        state.completion_pct = pct
        state.missing_information = pending
        state.ready_for_closure = ready

        if ready:
            return ClinicalDecision(
                action="closure",
                rationale="Pathway minimum clinical information collected.",
                missing_information=pending,
            )

        node = _select_next_node(state.pathway_id, answered)
        if node is None:
            state.ready_for_closure = True
            return ClinicalDecision(action="closure", rationale="All pathway nodes addressed.")

        if state.has_asked(node.topic_slug) or node.topic_slug in answered:
            return ClinicalDecision(action="closure", rationale="No unasked nodes remain.")

        return ClinicalDecision(
            action="ask",
            topic_slug=node.topic_slug,
            question_text=node.text,
            rationale=f"Pathway {state.pathway_id}: collect {node.clinical_info_label or node.topic_slug} before closure.",
            missing_information=pending,
        )

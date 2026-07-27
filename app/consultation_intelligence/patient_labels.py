"""Map internal topic slugs to natural Uzbek for patient-facing text."""

from __future__ import annotations

from app.clinical_brain.clinical_pathways import get_pathway
from app.consultation_intelligence.state import CollectedFact, ConsultationState


def topic_label_uz(state: ConsultationState, topic_slug: str) -> str:
    if topic_slug == "opening_complaint":
        return "Asosiy shikoyat"
    pathway = get_pathway(state.pathway_id)
    if pathway:
        for node in pathway.nodes:
            if node.topic_slug == topic_slug:
                label = (node.question_focus or node.question_uz or "").strip()
                if label:
                    return label.rstrip("?").strip()
    return "Ma'lumot"


def format_fact_for_patient(state: ConsultationState, fact: CollectedFact) -> str:
    label = topic_label_uz(state, fact.topic_slug)
    value = (fact.parsed_value or fact.raw_answer or "").strip()
    if not value:
        return ""
    return f"{label}: {value[:120]}"

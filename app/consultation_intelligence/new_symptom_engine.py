"""NewSymptomEngine — detect and merge added symptoms during active consultation."""

from __future__ import annotations

import re

from app.clinical_brain.clinical_pathways import get_pathway, recognize_pathway
from app.clinical_brain.senior_neurologist import detect_complaint_clusters
from app.consultation_intelligence.state import ConsultationState


def is_additive_symptom_message(text: str) -> bool:
    """True when patient adds a symptom rather than answering the pending question."""
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if re.search(r"\bham\b", lowered):
        return True
    return any(p in lowered for p in ("bilan birga", "qo'shimcha", "yana bir", "bundan tashqari"))


def detect_new_symptoms(message: str, state: ConsultationState) -> list:
    """Return complaint clusters not covered by the primary pathway category."""
    if not state.pathway_locked:
        return []
    clusters = detect_complaint_clusters(message)
    primary = state.base_category
    return [c for c in clusters if c.category != primary]


def _priority_nodes(pathway_id: str, limit: int = 2) -> list[tuple[str, str]]:
    """Return (topic_slug, question_text) for the most clinically important nodes."""
    pathway = get_pathway(pathway_id)
    if not pathway:
        return []
    chosen: list[tuple[str, str]] = []
    for node in pathway.nodes:
        if node.phase == "triage":
            chosen.append((node.topic_slug, node.text))
            break
    for node in pathway.nodes:
        if node.phase in ("discriminator", "narrative") and node.topic_slug not in {s for s, _ in chosen}:
            chosen.append((node.topic_slug, node.text))
            if len(chosen) >= limit:
                break
    if not chosen:
        for node in pathway.nodes[:limit]:
            chosen.append((node.topic_slug, node.text))
    return chosen[:limit]


def merge_new_symptoms(message: str, state: ConsultationState) -> str | None:
    """
    Merge newly reported symptoms into state.
    Returns Uzbek acknowledgment label(s) if merged, else None.
    """
    new_clusters = detect_new_symptoms(message, state)
    if not new_clusters:
        return None

    existing_cats = {str(s.get("category")) for s in state.secondary_symptoms}
    queued_slugs = {q["topic_slug"] for q in state.supplemental_questions}
    ack_labels: list[str] = []

    for cluster in new_clusters:
        if cluster.category in existing_cats:
            continue

        pathway_id, _, _ = recognize_pathway(message, category_hint=cluster.category)
        pathway = get_pathway(pathway_id)
        if not pathway:
            continue

        state.secondary_symptoms.append(
            {
                "category": cluster.category,
                "label_uz": cluster.label_uz,
                "pathway_id": pathway_id,
                "source_message": message[:200],
            }
        )
        existing_cats.add(cluster.category)

        fact_slug = f"secondary_symptom_{cluster.category}"
        if fact_slug not in state.answered_slugs:
            state.record_answer(fact_slug, message, cluster.label_uz)

        for orig_slug, question_text in _priority_nodes(pathway_id):
            supp_slug = f"supp:{pathway_id}:{orig_slug}"
            if state.has_asked(supp_slug) or supp_slug in queued_slugs:
                continue
            state.supplemental_questions.append(
                {
                    "topic_slug": supp_slug,
                    "question_text": question_text,
                    "source_label": cluster.label_uz,
                    "pathway_id": pathway_id,
                }
            )
            queued_slugs.add(supp_slug)

        ack_labels.append(cluster.label_uz)

    if not ack_labels:
        return None
    return ", ".join(ack_labels)

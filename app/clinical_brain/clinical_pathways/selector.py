"""Dynamic pathway selection — next question depends on prior answers."""

from __future__ import annotations

import re
from typing import Any

from app.clinical_brain.clinical_pathways.registry import get_pathway
from app.clinical_brain.clinical_pathways.recognition import recognize_pathway
from app.clinical_brain.clinical_pathways.types import PathwayContext, PathwayNode
from app.domain.consultation import ComplaintCategory


def _normalize(text: str) -> str:
    return text.lower().replace("'", "'").replace("'", "'")


def _topics_set(topics_covered: list[str], known_facts: dict[str, Any]) -> set[str]:
    merged = set(topics_covered or [])
    for item in known_facts.get("topics_covered") or []:
        if str(item).strip():
            merged.add(str(item))
    for item in known_facts.get("answered_topics") or []:
        if str(item).strip():
            merged.add(str(item))
    return merged


def _dependencies_met(node: PathwayNode, covered: set[str]) -> bool:
    return all(dep in covered for dep in node.depends_on)


def _select_next_node(pathway_nodes: tuple[PathwayNode, ...], covered: set[str]) -> PathwayNode | None:
    for node in pathway_nodes:
        if node.topic_slug in covered:
            continue
        if not _dependencies_met(node, covered):
            continue
        return node
    return None


def _compute_completion(pathway, covered: set[str]) -> tuple[list[str], list[str], float, bool]:
    required_slugs = [n.topic_slug for n in pathway.nodes if n.required]
    completed = [slug for slug in required_slugs if slug in covered]
    pending = [slug for slug in required_slugs if slug not in covered]
    total = len(required_slugs) or 1
    pct = len(completed) / total * 100.0
    min_met = len(completed) >= min(pathway.min_required_topics, total)
    triage_slugs = {n.topic_slug for n in pathway.nodes if n.phase == "triage"}
    triage_done = bool(triage_slugs & covered) or not triage_slugs
    ready = min_met and triage_done and len(completed) >= pathway.min_required_topics
    return completed, pending, pct, ready


def build_pathway_context(
    *,
    message: str,
    session_messages: list[dict[str, str]] | None = None,
    known_facts: dict[str, Any] | None = None,
    topics_covered: list[str] | None = None,
    category_hint: ComplaintCategory | str = "other_neurological",
    detected_red_flags: list[str] | None = None,
) -> PathwayContext:
    """Recognize syndrome, activate pathway, select next disease-specific question node."""
    facts = dict(known_facts or {})
    topics = list(topics_covered or [])
    covered = _topics_set(topics, facts)

    narrative = message or ""
    if session_messages:
        user_parts = [m["content"] for m in session_messages if m.get("role") == "user" and m.get("content")]
        if user_parts:
            narrative = " ".join(user_parts)

    pathway_id, confidence, rationale = recognize_pathway(
        narrative,
        category_hint=category_hint,
        known_facts=facts,
    )
    pathway = get_pathway(pathway_id)
    if not pathway:
        pathway = get_pathway("general_neurology")
        pathway_id = "general_neurology"
        rationale = "Fallback: umumiy nevrologik pathway."

    assert pathway is not None

    if detected_red_flags and pathway.id not in {"stroke_acute", "epilepsy"}:
        lowered = _normalize(narrative)
        for pid in ("stroke_acute", "epilepsy"):
            alt = get_pathway(pid)
            if alt and any(re.search(p, lowered) for p in alt.recognition_patterns):
                pathway = alt
                pathway_id = alt.id
                rationale = f"Qizil bayroq — {alt.syndrome_label_uz} pathwayiga o'tkazildi."
                break

    current = _select_next_node(pathway.nodes, covered)
    completed, pending, pct, ready = _compute_completion(pathway, covered)
    required_count = len([n for n in pathway.nodes if n.required])

    return PathwayContext(
        pathway_id=pathway.id,
        syndrome=pathway.syndrome,
        syndrome_label_uz=pathway.syndrome_label_uz,
        base_category=pathway.base_category,
        recognition_confidence=confidence,
        recognition_rationale=rationale,
        current_node=current,
        completed_topics=completed,
        pending_required_topics=pending,
        completion_pct=pct,
        ready_for_closure=ready,
        total_required=required_count,
    )


def apply_pathway_closure_gate(ctx: PathwayContext, *, ready_for_summary: bool, stop_asking: bool) -> tuple[bool, bool]:
    """Do not finish consultation until pathway has enough clinical information."""
    if not ctx.ready_for_closure:
        return False, False
    return ready_for_summary, stop_asking

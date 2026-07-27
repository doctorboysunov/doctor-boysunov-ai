"""Select the next question that maximizes diagnostic information gain."""

from __future__ import annotations

import re

from app.clinical_brain.clinical_pathways import get_pathway
from app.clinical_brain.clinical_pathways.types import PathwayNode
from app.consultation_intelligence.differential_engine import compute_uncertainty
from app.consultation_intelligence.pathway_knowledge import get_reasoning_profile
from app.consultation_intelligence.state import ConsultationState

_PHASE_WEIGHT = {"triage": 100.0, "discriminator": 80.0, "narrative": 55.0, "context": 35.0, "closure": 0.0}


def _dependencies_met(node: PathwayNode, answered: set[str]) -> bool:
    return all(dep in answered for dep in node.depends_on)


def _topic_matches_pattern(topic_slug: str, pattern: str) -> bool:
    if topic_slug in pattern:
        return True
    return any(part in topic_slug for part in pattern.split("|") if part)


def _rules_for_topic(profile, topic_slug: str) -> list:
    if not profile:
        return []
    return [r for r in profile.evidence_rules if _topic_matches_pattern(topic_slug, r.topic_pattern)]


def _diagnoses_affected(profile, topic_slug: str) -> set[str]:
    affected: set[str] = set()
    for rule in _rules_for_topic(profile, topic_slug):
        affected.update(rule.boosts.keys())
        affected.update(rule.suppresses.keys())
    return affected


def diagnostic_purpose(state: ConsultationState, node: PathwayNode) -> str:
    """Explain which diagnoses this question helps distinguish — every question has a purpose."""
    profile = get_reasoning_profile(state.pathway_id)
    affected = _diagnoses_affected(profile, node.topic_slug)
    differential = state.differential or []

    if node.phase == "triage":
        must_not_miss = [d["name"] for d in differential if d.get("must_not_miss")][:2]
        if must_not_miss:
            return f"Qizil bayroq skriningi — {', '.join(must_not_miss)} ni istisno qilish"
        return "Xavfli sabablarni istisno qilish (triage)"

    if affected:
        names = ", ".join(sorted(affected)[:3])
        return f"Ayiruvchi ma'lumot — {names} o'rtasida farqlash"

    if node.phase == "discriminator" and len(differential) >= 2:
        return (
            f"{differential[0].get('name', 'Asosiy')} va "
            f"{differential[1].get('name', 'muqobil')} o'rtasida farqlash"
        )

    label = node.clinical_info_label or node.topic_slug
    return f"Klinik suratni aniqlashtirish — {label}"


def _score_node(
    node: PathwayNode,
    state: ConsultationState,
    uncertainty: float,
) -> float:
    score = _PHASE_WEIGHT.get(node.phase, 40.0)
    profile = get_reasoning_profile(state.pathway_id)
    rules = _rules_for_topic(profile, node.topic_slug)
    score += len(rules) * 14.0

    differential = state.differential or []
    affected = _diagnoses_affected(profile, node.topic_slug)

    # Boost questions that help rule out active must-not-miss diagnoses
    for dx in differential:
        if not dx.get("must_not_miss"):
            continue
        if str(dx.get("exclusion_status") or "") in {"excluded", "ruled_out"}:
            continue
        if float(dx.get("probability_pct") or 0) >= 12.0 and dx.get("name") in affected:
            score += 35.0

    # Boost questions that split the top two competing diagnoses
    if len(differential) >= 2:
        top, second = differential[0], differential[1]
        gap = float(top.get("probability_pct") or 0) - float(second.get("probability_pct") or 0)
        if gap < 15.0:
            if top.get("name") in affected or second.get("name") in affected:
                score += 30.0
            if node.phase == "discriminator":
                score += 20.0

    if uncertainty > 0.5 and node.phase == "discriminator":
        score += 25.0
    if uncertainty > 0.7:
        score += 15.0

    if node.phase == "triage" and node.topic_slug not in state.answered_slugs:
        score += 50.0

    return score


def score_candidate_nodes(state: ConsultationState) -> list[tuple[PathwayNode, float, str]]:
    """Rank eligible nodes by diagnostic value with stated purpose."""
    pathway = get_pathway(state.pathway_id)
    if not pathway:
        return []

    answered = set(state.answered_slugs)
    uncertainty = float((state.clinical_assessment or {}).get("uncertainty_score", 0.5))
    if not state.clinical_assessment and state.differential:
        uncertainty = compute_uncertainty(state.differential)

    scored: list[tuple[PathwayNode, float, str]] = []
    for node in pathway.nodes:
        if node.topic_slug in answered:
            continue
        if not _dependencies_met(node, answered):
            continue
        purpose = diagnostic_purpose(state, node)
        scored.append((node, _score_node(node, state, uncertainty), purpose))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def select_best_node(state: ConsultationState) -> tuple[PathwayNode, str] | None:
    """Return highest-value node and its diagnostic purpose."""
    scored = score_candidate_nodes(state)
    if not scored:
        return None
    node, _, purpose = scored[0]
    return node, purpose


def mandatory_topics_unanswered(state: ConsultationState) -> list[str]:
    pathway = get_pathway(state.pathway_id)
    if not pathway:
        return []
    answered = set(state.answered_slugs)
    return [n.topic_slug for n in pathway.nodes if n.required and n.topic_slug not in answered]

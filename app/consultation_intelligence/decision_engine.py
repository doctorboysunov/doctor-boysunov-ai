"""DecisionEngine — evidence-driven question selection and pre-closure verification."""

from __future__ import annotations

from dataclasses import dataclass

from app.clinical_brain.clinical_pathways import get_pathway
from app.consultation_intelligence.closure_verifier import assess_closure_readiness
from app.consultation_intelligence.contradiction_detector import detect_contradictions
from app.consultation_intelligence.question_selector import (
    select_best_node,
    select_best_node_among,
    select_extra_probe,
)
from app.consultation_intelligence.state import ConsultationState, EmergencyStatus


@dataclass(frozen=True)
class ClinicalDecision:
    action: str  # ask | closure | emergency
    topic_slug: str = ""
    question_text: str = ""
    rationale: str = ""
    diagnostic_purpose: str = ""
    missing_information: list[str] | None = None


def _select_supplemental_node(state: ConsultationState) -> tuple[str, str, str] | None:
    answered = set(state.answered_slugs)
    for q in state.supplemental_questions:
        slug = str(q.get("topic_slug") or "")
        if slug and slug not in answered:
            return slug, str(q.get("question_text") or ""), str(q.get("source_label") or "")
    return None


def _pathway_progress(pathway_id: str, answered: set[str]) -> tuple[float, list[str]]:
    pathway = get_pathway(pathway_id)
    if not pathway:
        return 0.0, []
    required = [n for n in pathway.nodes if n.required]
    completed = [n for n in required if n.topic_slug in answered]
    pending = [n.topic_slug for n in required if n.topic_slug not in answered]
    pct = len(completed) / max(len(required), 1) * 100.0
    return pct, pending


def _node_for_slug(pathway_id: str, slug: str):
    pathway = get_pathway(pathway_id)
    if not pathway:
        return None
    for node in pathway.nodes:
        if node.topic_slug == slug:
            return node
    return None


class DecisionEngine:
    """Choose next action only when evidence supports closure — otherwise keep collecting."""

    def decide(self, state: ConsultationState) -> ClinicalDecision:
        if state.emergency_status == EmergencyStatus.CONFIRMED:
            return ClinicalDecision(
                action="emergency",
                rationale="Confirmed red flags require emergency evaluation.",
            )

        answered = set(state.answered_slugs)
        pct, pending = _pathway_progress(state.pathway_id, answered)
        state.completion_pct = pct
        state.missing_information = pending

        readiness = assess_closure_readiness(state)
        state.ready_for_closure = readiness.ready

        if readiness.ready:
            state.clinical_assessment = dict(state.clinical_assessment or {})
            state.clinical_assessment["closure_confidence"] = "confident"
            return ClinicalDecision(
                action="closure",
                rationale=(
                    "Evidence sufficient: mandatory questions complete, red flags checked, "
                    "alternatives reasonably excluded, differential confidently distinguished."
                ),
                missing_information=[],
            )

        remaining = list(readiness.remaining_topics)

        pending_clar = state.pending_clarification
        if pending_clar:
            slug = str(pending_clar.get("topic_slug") or "")
            if slug and slug not in answered:
                return ClinicalDecision(
                    action="ask",
                    topic_slug=slug,
                    question_text=str(pending_clar.get("question_text") or ""),
                    rationale=f"Clarify contradiction: {pending_clar.get('code', '')}.",
                    diagnostic_purpose="Nomuvofiqlikni aniqlashtirish — xulosa uchun zarur",
                    missing_information=remaining,
                )

        contradiction = detect_contradictions(state)
        if contradiction and contradiction.topic_slug not in answered:
            state.pending_clarification = {
                "code": contradiction.code,
                "topic_slug": contradiction.topic_slug,
                "question_text": contradiction.clarification_question,
            }
            return ClinicalDecision(
                action="ask",
                topic_slug=contradiction.topic_slug,
                question_text=contradiction.clarification_question,
                rationale=f"Resolve clinical contradiction ({contradiction.code}).",
                diagnostic_purpose="Ma'lumotlardagi ziddiyatni bartaraf etish",
                missing_information=remaining,
            )

        supp = _select_supplemental_node(state)
        if supp:
            slug, text, source = supp
            return ClinicalDecision(
                action="ask",
                topic_slug=slug,
                question_text=text,
                rationale=f"New symptom ({source}) — collect evidence before concluding.",
                diagnostic_purpose=f"Qo'shimcha belgi ({source}) bo'yicha ayiruvchi ma'lumot",
                missing_information=remaining,
            )

        # Prioritize remaining mandatory / red-flag / competing-dx topics — but the
        # ONE actually asked next is chosen adaptively by diagnostic value (which
        # active must-not-miss it helps exclude, whether it splits two close
        # competing diagnoses, how much it reduces uncertainty), not by the fixed
        # order the topics happen to be declared in the pathway.
        if remaining:
            picked = select_best_node_among(state, remaining)
            if picked is None:
                # Dependencies not yet satisfied for any remaining node (e.g. still
                # waiting on the screening question) — fall back to declared order.
                slug = remaining[0]
                node = _node_for_slug(state.pathway_id, slug)
                purpose = ""
                if node:
                    from app.consultation_intelligence.question_selector import diagnostic_purpose

                    purpose = diagnostic_purpose(state, node)
            else:
                node, purpose = picked
            if node:
                blocker = readiness.blockers[0] if readiness.blockers else "evidence_collection"
                return ClinicalDecision(
                    action="ask",
                    topic_slug=node.topic_slug,
                    question_text=node.text,
                    rationale=f"Evidence incomplete ({blocker}) — continue differential workup.",
                    diagnostic_purpose=purpose,
                    missing_information=remaining,
                )

        best = select_best_node(state)
        if best is None:
            # The pathway's own registry questions are exhausted. Never force a
            # confident-sounding closure on thin evidence — a senior neurologist
            # keeps probing with a few more genuinely useful differentiators
            # first (bounded, so this can't loop forever).
            if not readiness.ready:
                extra = select_extra_probe(state)
                if extra:
                    slug, text, purpose = extra
                    return ClinicalDecision(
                        action="ask",
                        topic_slug=slug,
                        question_text=text,
                        rationale=(
                            "Pathway questions exhausted but evidence still insufficient "
                            f"({readiness.blockers[0] if readiness.blockers else 'uncertain'}) — "
                            "continue with broader differentiators."
                        ),
                        diagnostic_purpose=purpose,
                        missing_information=remaining,
                    )
                state.clinical_assessment = dict(state.clinical_assessment or {})
                state.clinical_assessment["closure_confidence"] = "hedged"
            return ClinicalDecision(
                action="closure",
                rationale="No further high-value questions; pathway exhausted.",
                missing_information=remaining,
            )

        node, purpose = best
        assessment = state.clinical_assessment or {}
        leading = assessment.get("leading_diagnosis", "?")
        gap = assessment.get("leading_gap_pct", 0)

        return ClinicalDecision(
            action="ask",
            topic_slug=node.topic_slug,
            question_text=node.text,
            rationale=(
                f"Continue evidence collection — leading: {leading} "
                f"(gap {gap}%, uncertainty {assessment.get('uncertainty_score', '?')})."
            ),
            diagnostic_purpose=purpose,
            missing_information=remaining,
        )

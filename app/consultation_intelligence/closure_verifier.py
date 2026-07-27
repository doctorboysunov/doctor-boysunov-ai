"""Pre-closure verification — mandatory questions, red flags, exclusion, evidence sufficiency."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.clinical_brain.clinical_pathways import get_pathway
from app.clinical_brain.clinical_pathways.types import PathwayNode
from app.consultation_intelligence.differential_engine import compute_uncertainty
from app.consultation_intelligence.pathway_knowledge import get_reasoning_profile
from app.consultation_intelligence.state import ConsultationState

# Outpatient neurologist confidence thresholds
MIN_LEADING_GAP_PCT = 15.0
MAX_UNCERTAINTY = 0.40
MUST_NOT_MISS_ACTIVE_PCT = 12.0
MUST_NOT_MISS_EXCLUDED_PCT = 8.0
MIN_CLINICAL_FACTS = 4


@dataclass(frozen=True)
class ClosureReadiness:
    ready: bool
    checks: dict[str, bool]
    blockers: tuple[str, ...]
    remaining_topics: tuple[str, ...] = ()
    diagnostic_gaps: tuple[str, ...] = ()


def _answered_clinical_facts(state: ConsultationState) -> set[str]:
    skip_prefixes = ("opening_complaint", "clarify_", "secondary_symptom_")
    return {
        s
        for s in state.answered_slugs
        if s and not any(s.startswith(p) for p in skip_prefixes)
    }


def _mandatory_missing(pathway, answered: set[str]) -> list[str]:
    return [n.topic_slug for n in pathway.nodes if n.required and n.topic_slug not in answered]


def _red_flag_missing(pathway, answered: set[str]) -> list[str]:
    return [n.topic_slug for n in pathway.nodes if n.phase == "triage" and n.topic_slug not in answered]


def _pending_must_rule_out(differential: list[dict]) -> list[str]:
    pending: list[str] = []
    for dx in differential:
        if not dx.get("must_not_miss"):
            continue
        pct = float(dx.get("probability_pct") or 0)
        status = str(dx.get("exclusion_status") or "")
        if pct >= MUST_NOT_MISS_ACTIVE_PCT and status not in {"excluded", "ruled_out"}:
            pending.append(str(dx.get("name") or ""))
    return [x for x in pending if x]


def _competing_diagnoses_unresolved(differential: list[dict], answered: set[str], pathway) -> list[str]:
    """Top two diagnoses still too close — need more discriminators."""
    if len(differential) < 2:
        return []
    top = float(differential[0].get("probability_pct") or 0)
    second = float(differential[1].get("probability_pct") or 0)
    if top - second >= MIN_LEADING_GAP_PCT:
        return []

    unresolved: list[str] = []
    for node in pathway.nodes:
        if node.phase != "discriminator":
            continue
        if node.topic_slug in answered:
            continue
        if node.required:
            unresolved.append(node.topic_slug)
    return unresolved


def assess_closure_readiness(state: ConsultationState) -> ClosureReadiness:
    """
    Internal neurologist checklist before final assessment:
    mandatory complete, red flags checked, alternatives excluded, evidence sufficient.
    """
    pathway = get_pathway(state.pathway_id)
    if not pathway:
        return ClosureReadiness(
            ready=True,
            checks={"mandatory_complete": True, "red_flags_checked": True, "alternatives_excluded": True, "evidence_sufficient": True},
            blockers=(),
        )

    answered = set(state.answered_slugs)
    differential = state.differential or []
    assessment = state.clinical_assessment or {}

    mandatory_missing = _mandatory_missing(pathway, answered)
    triage_missing = _red_flag_missing(pathway, answered)
    pending_rule_out = _pending_must_rule_out(differential)
    competing_unresolved = _competing_diagnoses_unresolved(differential, answered, pathway)

    for q in state.supplemental_questions:
        slug = str(q.get("topic_slug") or "")
        if slug and slug not in answered:
            mandatory_missing.append(slug)

    gap = float(assessment.get("leading_gap_pct") or 0)
    if not gap and len(differential) >= 2:
        gap = float(differential[0].get("probability_pct") or 0) - float(differential[1].get("probability_pct") or 0)

    uncertainty = float(assessment.get("uncertainty_score") or compute_uncertainty(differential))
    evidence_rules = int(assessment.get("evidence_rules_applied") or 0)
    leading_evidence = str(assessment.get("supporting_evidence") or "").strip()
    clinical_fact_count = len(_answered_clinical_facts(state))

    mandatory_complete = len(mandatory_missing) == 0
    red_flags_checked = len(triage_missing) == 0
    alternatives_excluded = len(pending_rule_out) == 0

    evidence_sufficient = (
        gap >= MIN_LEADING_GAP_PCT
        and uncertainty <= MAX_UNCERTAINTY
        and clinical_fact_count >= MIN_CLINICAL_FACTS
        and (bool(leading_evidence) or evidence_rules >= 1)
        and len(competing_unresolved) == 0
    )

    checks = {
        "mandatory_complete": mandatory_complete,
        "red_flags_checked": red_flags_checked,
        "alternatives_excluded": alternatives_excluded,
        "evidence_sufficient": evidence_sufficient,
    }

    blockers: list[str] = []
    if not mandatory_complete:
        blockers.append(f"mandatory_questions_pending:{len(mandatory_missing)}")
    if not red_flags_checked:
        blockers.append(f"red_flag_screens_pending:{len(triage_missing)}")
    if not alternatives_excluded:
        blockers.append(f"must_not_miss_active:{','.join(pending_rule_out[:2])}")
    if gap < MIN_LEADING_GAP_PCT:
        blockers.append(f"leading_gap_insufficient:{gap:.0f}%")
    if uncertainty > MAX_UNCERTAINTY:
        blockers.append(f"uncertainty_high:{uncertainty:.2f}")
    if clinical_fact_count < MIN_CLINICAL_FACTS:
        blockers.append(f"insufficient_clinical_facts:{clinical_fact_count}")
    if competing_unresolved:
        blockers.append(f"competing_diagnoses_unresolved:{len(competing_unresolved)}")

    remaining = list(dict.fromkeys(mandatory_missing + triage_missing + competing_unresolved))

    diagnostic_gaps = list(pending_rule_out)
    if gap < MIN_LEADING_GAP_PCT and len(differential) >= 2:
        diagnostic_gaps.append(
            f"{differential[0].get('name', '?')} vs {differential[1].get('name', '?')}"
        )

    return ClosureReadiness(
        ready=all(checks.values()),
        checks=checks,
        blockers=tuple(blockers),
        remaining_topics=tuple(remaining),
        diagnostic_gaps=tuple(diagnostic_gaps),
    )


def ready_for_closure(state: ConsultationState) -> tuple[bool, list[str]]:
    """Compatibility wrapper — returns (ready, remaining topic slugs)."""
    readiness = assess_closure_readiness(state)
    return readiness.ready, list(readiness.remaining_topics)

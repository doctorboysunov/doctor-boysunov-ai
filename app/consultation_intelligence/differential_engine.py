"""Dynamic differential diagnosis — Bayesian-style updates after every patient answer."""

from __future__ import annotations

import re
from typing import Any

from app.clinical_brain.clinical_pathways import get_pathway
from app.consultation_intelligence.pathway_knowledge import (
    DiagnosisProfile,
    SyndromeReasoningProfile,
    get_reasoning_profile,
)
from app.consultation_intelligence.state import ConsultationState


def _normalize(text: str) -> str:
    return text.lower().replace("'", "'").replace("'", "'")


def _match_pattern(pattern: str, text: str) -> bool:
    return bool(re.search(pattern, _normalize(text), re.I))


def _default_profile(pathway_id: str) -> SyndromeReasoningProfile:
    pathway = get_pathway(pathway_id)
    names = list(pathway.differential_targets) if pathway and pathway.differential_targets else []
    if not names and pathway:
        names = [pathway.syndrome]
    if not names:
        names = ["Klinik suratga qarab aniqlanadi"]
    diagnoses = tuple(
        DiagnosisProfile(name, max(15.0, 50.0 - i * 10), must_not_miss=(i == 0))
        for i, name in enumerate(names[:5])
    )
    from app.consultation_intelligence.pathway_knowledge import SyndromeReasoningProfile

    return SyndromeReasoningProfile(
        pathway_id=pathway_id,
        diagnoses=diagnoses,
        evidence_rules=(),
        investigations={},
        treatment={},
        referral={},
    )


def _apply_evidence(
    weights: dict[str, float],
    profile: SyndromeReasoningProfile,
    facts: dict[str, str],
) -> tuple[dict[str, str], dict[str, int], set[str]]:
    """Apply evidence rules; return evidence map, rule counts, excluded dx names."""
    evidence_notes: dict[str, list[str]] = {d.name: [] for d in profile.diagnoses}
    rule_counts: dict[str, int] = {d.name: 0 for d in profile.diagnoses}
    suppressed: set[str] = set()

    for slug, val in facts.items():
        combined = f"{slug} {val}"
        for rule in profile.evidence_rules:
            if not _match_pattern(rule.topic_pattern, slug):
                continue
            if not _match_pattern(rule.value_pattern, combined):
                continue
            for dx, mult in rule.boosts.items():
                if dx in weights:
                    weights[dx] *= mult
                    evidence_notes.setdefault(dx, []).append(f"{slug}: {val[:80]}")
                    rule_counts[dx] = rule_counts.get(dx, 0) + 1
            for dx, mult in rule.suppresses.items():
                if dx in weights:
                    weights[dx] *= mult
                    suppressed.add(dx)
                    if mult <= 0.5:
                        rule_counts[dx] = rule_counts.get(dx, 0) + 1

    evidence_map = {k: "; ".join(v[:3]) for k, v in evidence_notes.items() if v}
    return evidence_map, rule_counts, suppressed


def update_differential(
    state: ConsultationState,
    facts: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Recompute ranked differential from prior state + all collected facts.
    Maintains continuity — each turn blends prior probabilities with new evidence.
    """
    facts = facts or state.fact_map()
    profile = get_reasoning_profile(state.pathway_id) or _default_profile(state.pathway_id)

    prior_map = {_normalize(d["name"]): float(d.get("probability_pct") or 0) for d in state.differential}

    weights: dict[str, float] = {}
    must_not_miss: set[str] = set()
    for dx in profile.diagnoses:
        key = dx.name
        prior = prior_map.get(_normalize(key), dx.prior_pct)
        weights[key] = max(0.5, 0.6 * prior + 0.4 * dx.prior_pct)
        if dx.must_not_miss:
            must_not_miss.add(key)

    evidence_map, rule_counts, suppressed = _apply_evidence(weights, profile, facts)

    for name in must_not_miss:
        weights[name] = max(weights.get(name, 5.0), 5.0)

    total = sum(weights.values()) or 1.0
    ranked: list[dict[str, Any]] = []
    for dx in profile.diagnoses:
        pct = round(100.0 * weights[dx.name] / total, 1)
        exclusion_status = _exclusion_status(
            dx.name, pct, dx.must_not_miss, dx.name in suppressed, evidence_map.get(dx.name, "")
        )
        ranked.append(
            {
                "name": dx.name,
                "probability_pct": pct,
                "must_not_miss": dx.must_not_miss,
                "supporting_evidence": evidence_map.get(dx.name, ""),
                "evidence_rule_count": rule_counts.get(dx.name, 0),
                "exclusion_status": exclusion_status,
                "rank": 0,
            }
        )

    ranked.sort(key=lambda x: x["probability_pct"], reverse=True)
    for i, item in enumerate(ranked):
        item["rank"] = i + 1
    return ranked


def _exclusion_status(
    name: str,
    pct: float,
    must_not_miss: bool,
    was_suppressed: bool,
    evidence: str,
) -> str:
    """Track whether alternative diagnoses have been reasonably excluded."""
    if was_suppressed or (evidence and "negative" in evidence.lower() and must_not_miss):
        return "ruled_out"
    if pct <= 8.0:
        return "excluded"
    if must_not_miss and pct >= 12.0:
        return "pending_rule_out"
    if pct >= 20.0:
        return "competing"
    return "possible"


def compute_uncertainty(differential: list[dict[str, Any]]) -> float:
    """0 = confident (one dominant dx), 1 = highly uncertain."""
    if not differential:
        return 1.0
    if len(differential) == 1:
        return 0.0
    top = float(differential[0].get("probability_pct") or 0)
    second = float(differential[1].get("probability_pct") or 0)
    gap = top - second
    return max(0.0, min(1.0, 1.0 - gap / 50.0))


def build_clinical_assessment(
    state: ConsultationState,
    differential: list[dict[str, Any]],
) -> dict[str, Any]:
    """Investigations, treatment, referral from top diagnosis and evidence."""
    profile = get_reasoning_profile(state.pathway_id) or _default_profile(state.pathway_id)
    top = differential[0]["name"] if differential else ""
    second = differential[1]["name"] if len(differential) > 1 else ""

    investigations: list[str] = []
    treatment: list[str] = []
    referral: str = ""

    for dx_name in (top, second):
        investigations.extend(profile.investigations.get(dx_name, ()))
        treatment.extend(profile.treatment.get(dx_name, ()))
        if not referral and dx_name in profile.referral:
            if float(differential[0].get("probability_pct") or 0) >= 20 or any(
                d.get("must_not_miss") for d in differential[:2]
            ):
                referral = profile.referral[dx_name]

    must_not_miss = [d["name"] for d in differential if d.get("must_not_miss") and d.get("rank", 99) <= 3]
    pending_rule_out = [d["name"] for d in differential if d.get("exclusion_status") == "pending_rule_out"]

    leading_pct = float(differential[0].get("probability_pct") or 0) if differential else 0
    second_pct = float(differential[1].get("probability_pct") or 0) if len(differential) > 1 else 0
    leading_gap = leading_pct - second_pct
    total_rules = sum(int(d.get("evidence_rule_count") or 0) for d in differential)
    closure_checks = _closure_checks(state, differential)

    return {
        "leading_diagnosis": top,
        "secondary_diagnosis": second,
        "leading_probability_pct": leading_pct,
        "leading_gap_pct": round(leading_gap, 1),
        "supporting_evidence": differential[0].get("supporting_evidence", "") if differential else "",
        "must_not_miss": must_not_miss,
        "pending_rule_out": pending_rule_out,
        "recommended_investigations": list(dict.fromkeys(investigations))[:4],
        "treatment_approach": list(dict.fromkeys(treatment))[:4],
        "referral_criteria": referral,
        "uncertainty_score": compute_uncertainty(differential),
        "evidence_rules_applied": total_rules,
        "closure_readiness": closure_checks,
    }


def _closure_checks(state: ConsultationState, differential: list[dict[str, Any]]) -> dict[str, bool]:
    from app.consultation_intelligence.closure_verifier import assess_closure_readiness

    # Pass current differential on state for accurate readiness (may differ mid-update)
    snapshot = ConsultationState.from_dict({**state.to_dict(), "differential": differential})
    return dict(assess_closure_readiness(snapshot).checks)

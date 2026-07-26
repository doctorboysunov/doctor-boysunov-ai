"""Resolve applicable guideline rules for a clinical case."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.medical_brain.evidence.catalog import GUIDELINE_RULES
from app.medical_brain.evidence.types import GuidelineRule


@dataclass(frozen=True)
class ResolvedRule:
    rule: GuidelineRule
    strength: str  # strong | weak


def _normalize(text: str) -> str:
    return (text or "").lower().replace("'", "'").replace("'", "'")


def _pattern_hits(rule: GuidelineRule, blob: str) -> bool:
    for pattern in rule.match_patterns:
        token = re.escape(pattern) if " " in pattern else pattern
        if re.search(token, blob, re.I):
            return True
    return False


def _ref_hits(rule: GuidelineRule, guideline_refs: list[str]) -> bool:
    for ref in guideline_refs:
        ref_l = _normalize(ref)
        if rule.source.lower() in ref_l:
            return True
        if rule.source_id.lower().replace("_", " ") in ref_l:
            return True
        title_words = [w for w in _normalize(rule.title).split() if len(w) > 4]
        if any(w in ref_l for w in title_words[:4]):
            return True
    return False


def _diagnosis_hits(rule: GuidelineRule, gold_diagnosis: str) -> bool:
    diag = _normalize(gold_diagnosis)
    return _pattern_hits(rule, diag)


def resolve_applicable_rules(
    *,
    specialty: str,
    gold_diagnosis: str,
    guideline_references: list[str],
    patient_text: str,
    max_rules: int = 6,
) -> list[GuidelineRule]:
    """Return guideline rules applicable to this case (strong matches prioritized)."""
    resolved = _resolve_with_strength(
        specialty=specialty,
        gold_diagnosis=gold_diagnosis,
        guideline_references=guideline_references,
        patient_text=patient_text,
        max_rules=max_rules,
    )
    return [r.rule for r in resolved]


def _resolve_with_strength(
    *,
    specialty: str,
    gold_diagnosis: str,
    guideline_references: list[str],
    patient_text: str,
    max_rules: int = 6,
) -> list[ResolvedRule]:
    blob = _normalize(" ".join([gold_diagnosis, " ".join(guideline_references), patient_text]))
    matched: list[ResolvedRule] = []
    seen: set[str] = set()

    for rule in GUIDELINE_RULES:
        if rule.rule_id in seen:
            continue

        strong = _ref_hits(rule, guideline_references) or _diagnosis_hits(rule, gold_diagnosis)
        weak = (
            not strong
            and specialty in rule.specialties
            and _pattern_hits(rule, blob)
        )

        if strong:
            matched.append(ResolvedRule(rule, "strong"))
            seen.add(rule.rule_id)
        elif weak:
            matched.append(ResolvedRule(rule, "weak"))
            seen.add(rule.rule_id)

    # Prefer diverse sources; strong before weak
    matched.sort(key=lambda r: (0 if r.strength == "strong" else 1, r.rule.source))
    if matched:
        return matched[:max_rules]

    # Last resort: one specialty-default rule tied to diagnosis keywords
    for rule in GUIDELINE_RULES:
        if specialty in rule.specialties and _pattern_hits(rule, _normalize(gold_diagnosis)):
            return [ResolvedRule(rule, "weak")]
    return []

"""Complaint recognition — map patient text to neurological syndrome / pathway."""

from __future__ import annotations

import re
from typing import Any

from app.clinical_brain.clinical_pathways.registry import (
    all_pathways,
    default_pathway_for_category,
    get_pathway,
)
from app.clinical_brain.clinical_pathways.types import ClinicalPathway, RecognitionConfidence
from app.domain.consultation import ComplaintCategory
from app.services.consultation_classifier import classify_complaint


def _normalize(text: str) -> str:
    return text.lower().replace("'", "'").replace("'", "'").replace("‘", "'").replace("’", "'")


def _score_pathway(pathway: ClinicalPathway, lowered: str) -> tuple[int, list[str]]:
    score = 0
    hits: list[str] = []
    for kw in pathway.recognition_keywords:
        if kw.lower() in lowered:
            score += 12
            hits.append(kw)
    for pattern in pathway.recognition_patterns:
        if re.search(pattern, lowered):
            score += 15
            hits.append(f"re:{pattern[:24]}")
    if score:
        score += pathway.priority // 10
    return score, hits


def _has_neck_signal(lowered: str) -> bool:
    return bool(re.search(r"bo['']?yin|boyin|servikal", lowered))


def _has_limb_numbness(lowered: str) -> bool:
    return bool(re.search(r"uyuq|qiynish|sezgi", lowered))


def recognize_pathway(
    text: str,
    *,
    category_hint: ComplaintCategory | str = "other_neurological",
    known_facts: dict[str, Any] | None = None,
) -> tuple[str, RecognitionConfidence, str]:
    """
    Return (pathway_id, confidence, rationale).
    Never leaves ambiguous cases as generic if a specific pathway matches.
    """
    facts = known_facts or {}
    persisted = str(facts.get("clinical_pathway_id") or "").strip()
    if persisted and get_pathway(persisted):
        return persisted, "high", "Sessionda faol klinik pathway saqlangan."

    lowered = _normalize(text or "")
    if not lowered:
        fallback = default_pathway_for_category(category_hint)
        return fallback, "low", "Matn bo'sh — kategoriya bo'yicha default pathway."

    # Disambiguate hand numbness: neck + arm → cervical; limb alone → peripheral
    if _has_limb_numbness(lowered):
        if _has_neck_signal(lowered):
            pathway = get_pathway("cervical_radiculopathy")
            if pathway:
                return (
                    "cervical_radiculopathy",
                    "high",
                    "Bo'yin + qo'l/uyuq belgisi — servikal radikulopatiya pathway.",
                )
        elif not re.search(r"oyoq|bel\s*og", lowered):
            pathway = get_pathway("peripheral_neuropathy")
            if pathway:
                return (
                    "peripheral_neuropathy",
                    "high",
                    "Uyuqlik bo'yin belgisiz — periferik neuropatiya pathway.",
                )

    if re.search(r"migren|migraine", lowered):
        pathway = get_pathway("migraine")
        if pathway:
            return "migraine", "high", "Migren pattern aniqlandi."

    if re.search(r"bell|yuz\s*qiysh", lowered):
        pathway = get_pathway("bell_palsy")
        if pathway:
            return "bell_palsy", "high", "Bell falaji pattern aniqlandi."

    ranked: list[tuple[int, ClinicalPathway, list[str]]] = []
    for pathway in all_pathways():
        if pathway.id == "general_neurology":
            continue
        score, hits = _score_pathway(pathway, lowered)
        if score > 0:
            ranked.append((score, pathway, hits))

    ranked.sort(key=lambda x: x[0], reverse=True)

    if ranked:
        best_score, best, hits = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else 0
        confidence: RecognitionConfidence = "high"
        if best_score < 25:
            confidence = "medium"
        if second_score >= best_score - 5 and second_score > 0:
            confidence = "medium"
        rationale = f"Aniqlangan sindrom: {best.syndrome_label_uz}. Signallar: {', '.join(hits[:4])}."
        return best.id, confidence, rationale

    classified = classify_complaint(text)
    if classified != "other_neurological":
        fallback_id = default_pathway_for_category(classified)
        pathway = get_pathway(fallback_id)
        label = pathway.syndrome_label_uz if pathway else classified
        return fallback_id, "medium", f"Klassifikator: {label} — mos pathway faollashtirildi."

    fallback = default_pathway_for_category(category_hint if category_hint != "other_neurological" else "unclassified_neurology")
    if fallback == "general_neurology":
        fallback = "unclassified_neurology"
    return fallback, "low", "Aniq signal topilmadi — nevrologik sindrom aniqlashtirilmoqda."


def resolve_complaint_category(
    text: str,
    *,
    category_hint: ComplaintCategory | str = "other_neurological",
    known_facts: dict[str, Any] | None = None,
) -> ComplaintCategory:
    """Replace generic other_neurological with pathway-specific category when possible."""
    pathway_id, _, _ = recognize_pathway(text, category_hint=category_hint, known_facts=known_facts)
    pathway = get_pathway(pathway_id)
    if pathway and pathway.base_category != "other_neurological":
        return pathway.base_category
    classified = classify_complaint(text)
    if classified != "other_neurological":
        return classified
    if pathway:
        return pathway.base_category
    return category_hint if category_hint in _VALID_CATEGORIES else "other_neurological"  # type: ignore[return-value]


_VALID_CATEGORIES: set[str] = {
    "headache", "low_back_pain", "neck_pain", "vertigo", "stroke",
    "neuropathy", "facial_nerve_palsy", "tremor", "memory_problems",
    "sleep_disorders", "anxiety", "depression", "other_neurological",
}

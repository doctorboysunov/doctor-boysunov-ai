"""Ranked differential diagnosis with numeric probability estimation and Bayesian updates."""

from __future__ import annotations

import re
from typing import Any

from app.clinical_brain.types import RankedHypothesis

_CATEGORICAL_BASE = {"high": 0.42, "medium": 0.24, "low": 0.12}

# Symptom-evidence multipliers — lightweight likelihood model (not exhaustive)
_EVIDENCE_LIKELIHOOD: tuple[tuple[str, tuple[str, ...], float], ...] = (
    (r"chest|ko['']?krak|yurak og", ("ACS", "myocardial", "angina", "PE", "pneumothorax"), 1.35),
    (r"nafas qis|bo['']?g['']?il|dyspnea", ("PE", "heart failure", "asthma", "COPD", "pneumonia", "ACS"), 1.3),
    (r"hemoptysis|qon tufla|yo['']?talda qon", ("TB", "PE", "pneumonia", "malignancy"), 1.45),
    (r"thunderclap|eng kuchli bosh|birdan juda kuchli", ("SAH", "subarachnoid", "stroke", "meningitis"), 1.5),
    (r"kuchsiz|uvish|nutq|focal", ("stroke", "TIA", "cord compression", "Guillain"), 1.4),
    (r"isitma|38|39|40|fever", ("infection", "sepsis", "pneumonia", "UTI", "meningitis"), 1.25),
    (r"qorin og['']?ri|abdominal", ("appendicitis", "cholecystitis", "pancreatitis", "obstruction"), 1.2),
    (r"qon ket|bleeding|melena|hematemesis", ("GI bleed", "ulcer", "varices", "hemorrhage"), 1.35),
    (r"meva hid|kussmaul|polyuria|diabet", ("DKA", "diabetes", "hyperglycemia"), 1.4),
    (r"purpura|petexi|oqmaydi", ("ITP", "meningococcemia", "vasculitis", "DIC"), 1.45),
    (r"homilador|pregnant", ("ectopic", "preeclampsia", "placenta", "obstetric"), 1.3),
)


def _normalize(text: str) -> str:
    return text.lower().replace("'", "'").replace("'", "'")


def _parse_probability_pct(data: dict[str, Any] | RankedHypothesis, *, fallback: str = "medium") -> float:
    if isinstance(data, RankedHypothesis):
        if data.probability_pct > 0:
            return data.probability_pct
        prob = data.probability
    else:
        raw_pct = data.get("probability_pct") or data.get("probability_value")
        if raw_pct is not None:
            try:
                val = float(raw_pct)
                return val * 100 if val <= 1.0 else val
            except (TypeError, ValueError):
                pass
        prob = str(data.get("probability") or fallback)
    try:
        val = float(prob)
        return val * 100 if val <= 1.0 else val
    except (TypeError, ValueError):
        return _CATEGORICAL_BASE.get(prob.lower(), 0.2) * 100


def _collect_hypotheses(
    hypotheses: list[RankedHypothesis],
    alternatives: list[RankedHypothesis],
    must_not_miss: list[RankedHypothesis],
) -> list[RankedHypothesis]:
    seen: set[str] = set()
    merged: list[RankedHypothesis] = []
    for group in (hypotheses, alternatives, must_not_miss):
        for h in group:
            key = _normalize(h.name)
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(h)
    return merged


def _prior_map(prior_differential: list[dict[str, Any] | RankedHypothesis]) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in prior_differential:
        if isinstance(item, RankedHypothesis):
            name = item.name
            pct = item.probability_pct or _parse_probability_pct(item)
        else:
            name = str(item.get("name") or "")
            pct = _parse_probability_pct(item)
        if name:
            result[_normalize(name)] = pct
    return result


def _evidence_multiplier(name: str, patient_text: str) -> float:
    norm_name = _normalize(name)
    combined = _normalize(patient_text)
    mult = 1.0
    for pattern, diagnoses, boost in _EVIDENCE_LIKELIHOOD:
        if re.search(pattern, combined, re.I):
            if any(d.lower() in norm_name for d in diagnoses):
                mult = max(mult, boost)
    return mult


def _new_symptom_shift(
    name: str,
    new_symptoms: list[str],
    *,
    must_not_miss: bool,
) -> float:
    if not new_symptoms:
        return 1.0
    norm = _normalize(name)
    shift = 1.0
    for sym in new_symptoms:
        s = _normalize(sym)
        if s in norm or any(s in d for d in ("stroke", "bleed", "sepsis", "PE", "ACS")):
            shift *= 1.15
    if must_not_miss and new_symptoms:
        shift *= 1.1
    return shift


def update_differential_probabilities(
    *,
    hypotheses: list[RankedHypothesis],
    alternatives: list[RankedHypothesis],
    must_not_miss: list[RankedHypothesis],
    prior_differential: list[dict[str, Any] | RankedHypothesis] | None = None,
    patient_text: str = "",
    new_symptoms: list[str] | None = None,
    is_emergency: bool = False,
) -> list[RankedHypothesis]:
    """Bayesian-style update: prior × evidence likelihood × model estimate → normalized posterior."""
    merged = _collect_hypotheses(hypotheses, alternatives, must_not_miss)
    if not merged:
        return []

    must_not_miss_names = {_normalize(h.name) for h in must_not_miss}
    priors = _prior_map(prior_differential or [])
    new_symptoms = new_symptoms or []

    weights: dict[str, float] = {}
    rationales: dict[str, str] = {}

    for h in merged:
        key = _normalize(h.name)
        model_pct = _parse_probability_pct(h)
        prior_pct = priors.get(key, model_pct * 0.85)

        # Blend prior and model estimate (physician re-ranks with new data)
        blended = 0.55 * prior_pct + 0.45 * model_pct
        blended *= _evidence_multiplier(h.name, patient_text)
        blended *= _new_symptom_shift(h.name, new_symptoms, must_not_miss=key in must_not_miss_names)

        if key in must_not_miss_names:
            blended = max(blended, 8.0)  # floor for rule-out diagnoses
        if is_emergency and any(w in key for w in ("emergency", "acs", "stroke", "sepsis", "pe ", "pulmonary")):
            blended *= 1.12

        weights[key] = max(blended, 0.5)
        rationales[key] = h.rationale

    total = sum(weights.values()) or 1.0
    ranked: list[RankedHypothesis] = []
    for h in merged:
        key = _normalize(h.name)
        pct = round(100 * weights[key] / total, 1)
        cat = "high" if pct >= 30 else "medium" if pct >= 12 else "low"
        ranked.append(
            RankedHypothesis(
                name=h.name,
                probability=cat,
                rationale=rationales.get(key, h.rationale),
                probability_pct=pct,
            )
        )

    ranked.sort(key=lambda x: x.probability_pct, reverse=True)
    return ranked


def format_differential_for_prompt(ranked: list[RankedHypothesis]) -> str:
    if not ranked:
        return "No prior differential — build from scratch this turn."
    parts = [f"{h.name} ({h.probability_pct}%)" for h in ranked[:6]]
    return "Current ranked differential (UPDATE with new information): " + "; ".join(parts)

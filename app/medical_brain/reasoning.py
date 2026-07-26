"""Physician-level clinical reasoning — engine-side context, contradictions, enrichment."""

from __future__ import annotations

import re
from typing import Any

from app.clinical_brain.types import RankedHypothesis
from app.medical_brain.differential import format_differential_for_prompt
from app.medical_brain.types import MedicalBrainInternal


def _normalize(text: str) -> str:
    return (
        text.lower()
        .replace("'", "'")
        .replace("'", "'")
        .replace("ʻ", "'")
    )


def extract_user_turns(session_messages: list[dict[str, str]]) -> list[str]:
    return [str(m.get("content") or "") for m in session_messages if m.get("role") == "user" and m.get("content")]


def extract_patient_context(
    known_facts: dict[str, Any],
    session_messages: list[dict[str, str]],
) -> dict[str, Any]:
    """Demographics and clinical context for adaptive questioning — no diagnosis labels."""
    profile = str(known_facts.get("profile") or known_facts.get("patient_profile") or "")
    combined = _normalize(" ".join(extract_user_turns(session_messages)) + " " + profile)

    ctx: dict[str, Any] = {
        "profile_text": profile or None,
        "age_group": None,
        "sex": None,
        "pregnant": False,
        "chronic_conditions": [],
        "medications": [],
        "prior_internal": known_facts.get("prior_internal") or {},
    }

    if re.search(r"bolam|bola|chaqaloq|farzand|infant|haftalik|oylik|yosh bol", combined):
        ctx["age_group"] = "pediatric"
    elif re.search(r"\b(7[0-9]|8[0-9]|9[0-9])\s*y|\b(7[0-9]|8[0-9]|9[0-9])y|elderly|qariya", combined):
        ctx["age_group"] = "elderly"
    elif re.search(r"\b(1[89]|[2-6][0-9])\s*y|\b(1[89]|[2-6][0-9])y", combined):
        ctx["age_group"] = "adult"

    if re.search(r"homilador|homiladorman|pregnant|\d+w pregnant|\d+ hafta homila", combined):
        ctx["pregnant"] = True
        ctx["sex"] = "female"

    if re.search(r"\berkak\b|male,", profile.lower()) or "male" in profile.lower():
        ctx["sex"] = "male"
    elif re.search(r"\bayol\b|female,", profile.lower()) or "female" in profile.lower():
        ctx["sex"] = "female"

    chronic_patterns = (
        (r"diabet|qandli diabet", "diabetes"),
        (r"astma|asthma", "asthma"),
        (r"gipert|hypertens|qon bosim", "hypertension"),
        (r"surunkali yo['']?tal|COPD", "COPD"),
        (r"insulin", "insulin use"),
        (r"steroid|predniz", "steroid use"),
        (r"antikoagul|warfarin|heparin", "anticoagulation"),
        (r"qandli diabet|diabet", "diabetes"),
    )
    for pattern, label in chronic_patterns:
        if re.search(pattern, combined) and label not in ctx["chronic_conditions"]:
            ctx["chronic_conditions"].append(label)

    if re.search(r"ko['']?p dori|tabletka|insulin|antibiotik|dori ich", combined):
        ctx["medications"].append("mentioned medications")

    return ctx


def detect_contradictions(user_turns: list[str]) -> list[str]:
    """Flag timeline or severity contradictions between patient turns."""
    if len(user_turns) < 2:
        return []

    contradictions: list[str] = []
    combined = _normalize(" ".join(user_turns))

    # Duration mismatch: "1 hafta" then "aslida 3 kun"
    if re.search(r"1 hafta|bir hafta", user_turns[0].lower()) and re.search(
        r"aslida \d+ kun|faqat \d+ kun", _normalize(user_turns[-1])
    ):
        contradictions.append("Duration estimate changed — clarify true onset")

    # Severity minimization then escalation
    if re.search(r"oddiy|shunchaki|deb o['']?ylayman|kam", _normalize(user_turns[0])) and re.search(
        r"aslida|lekin|asl holatda|juda|qattiq|40|39", _normalize(user_turns[-1])
    ):
        contradictions.append("Patient initially minimized symptoms — verify severity")

    # Fever denied then admitted
    if re.search(r"isitma yo['']?q|isitmasi yo['']?q", _normalize(user_turns[0])) and re.search(
        r"isitma \d|39|40|fever", combined
    ):
        contradictions.append("Fever status contradicted — clarify current temperature")

    # Pain severity shift
    if re.search(r"yengil|ozgina|tinch", _normalize(user_turns[0])) and re.search(
        r"eng kuchli|hayotimdagi|birdan juda|chidab bo['']?lmaydigan", combined
    ):
        contradictions.append("Pain severity escalated — clarify character and timing")

    return contradictions


def detect_new_symptoms(user_turns: list[str]) -> list[str]:
    """Symptom tokens appearing only in the latest turn."""
    if len(user_turns) < 2:
        return []

    prior = _normalize(" ".join(user_turns[:-1]))
    latest = _normalize(user_turns[-1])
    candidates = (
        "qon", "qusish", "hush", "nafas qis", "ko'krak og", "titroq", "uvish",
        "ko'rmay", "eshitmay", "isitma", "shish", "siydik", "qorin og",
    )
    return [c for c in candidates if c in latest and c not in prior]


def extract_answered_topics(session_messages: list[dict[str, str]], topics_covered: list[str]) -> list[str]:
    """Topics already addressed in conversation — do not re-ask."""
    answered = list(topics_covered)
    combined = _normalize(" ".join(extract_user_turns(session_messages)))

    topic_signals = {
        "onset_timing": r"qachon|kun|hafta|soat|boshlandi|oldin",
        "fever": r"isitma|temperatura|38|39|40",
        "pain_character": r"og'riq|ogriq|kuchli|tarqal",
        "breathing": r"nafas|hushtak|nafas qis",
        "bleeding": r"qon",
        "pregnancy_status": r"homilador|homiladorlik testi",
        "medication": r"dori|tabletka|insulin",
        "trauma": r"yiqil|travma|urildi",
        "urinary": r"siydik|hojatxona",
        "neuro_deficit": r"kuchsiz|uvish|nutq|ishlamay",
    }
    for topic, pattern in topic_signals.items():
        if re.search(pattern, combined) and topic not in answered:
            answered.append(topic)
    return answered


def compute_emergency_probability(
    *,
    detected_flags: list[str],
    is_emergency: bool,
    assessment: str = "",
) -> float:
    prob = 0.15
    if detected_flags:
        prob += min(0.45, 0.12 * len(detected_flags))
    if is_emergency:
        prob += 0.25
    assess = (assessment or "").lower()
    if assess in {"emergency", "urgent", "shoshilinch"}:
        prob = max(prob, 0.85 if assess == "emergency" else 0.65)
    return round(min(1.0, prob), 2)


def build_story_synthesis(user_turns: list[str], known_facts: dict[str, Any]) -> str:
    if not user_turns:
        return ""
    parts = [f"Turn {i + 1}: {t.strip()}" for i, t in enumerate(user_turns) if t.strip()]
    profile = known_facts.get("profile") or known_facts.get("patient_profile")
    if profile:
        parts.insert(0, f"Profile: {profile}")
    return " | ".join(parts)


def build_reasoning_context(
    *,
    known_facts: dict[str, Any],
    session_messages: list[dict[str, str]],
    topics_covered: list[str],
    detected_flags: list[str],
    is_emergency: bool,
    primary_specialty: str,
    secondary_specialties: list[str],
) -> dict[str, Any]:
    user_turns = extract_user_turns(session_messages)
    patient_ctx = extract_patient_context(known_facts, session_messages)
    contradictions = detect_contradictions(user_turns)
    new_symptoms = detect_new_symptoms(user_turns)
    answered = extract_answered_topics(session_messages, topics_covered)
    prior_internal = known_facts.get("prior_internal") or {}
    prior_ranked = prior_internal.get("ranked_differential") or prior_internal.get("step3_hypotheses") or []

    return {
        "patient_context": patient_ctx,
        "story_synthesis": build_story_synthesis(user_turns, known_facts),
        "contradictions_to_clarify": contradictions,
        "new_symptoms_this_turn": new_symptoms,
        "answered_topics": answered,
        "prior_hypotheses": prior_ranked,
        "prior_internal": prior_internal,
        "detected_red_flags": detected_flags,
        "emergency_probability": compute_emergency_probability(
            detected_flags=detected_flags,
            is_emergency=is_emergency,
            assessment=str(prior_internal.get("step4_emergency_assessment") or ""),
        ),
        "recommended_specialty": primary_specialty,
        "recommended_secondary": secondary_specialties,
        "multi_turn": len(user_turns) > 1,
    }


def format_reasoning_block(ctx: dict[str, Any]) -> str:
    """Inject into physician prompt — guides adaptive reasoning without revealing answers."""
    lines = ["CLINICAL REASONING CONTEXT (use to think — not to recite to patient):"]

    if ctx.get("story_synthesis"):
        lines.append(f"Whole story so far: {ctx['story_synthesis']}")

    pc = ctx.get("patient_context") or {}
    adapt_parts = []
    if pc.get("age_group"):
        adapt_parts.append(f"age_group={pc['age_group']}")
    if pc.get("sex"):
        adapt_parts.append(f"sex={pc['sex']}")
    if pc.get("pregnant"):
        adapt_parts.append("pregnant=yes")
    if pc.get("chronic_conditions"):
        adapt_parts.append(f"chronic={', '.join(pc['chronic_conditions'])}")
    if pc.get("medications"):
        adapt_parts.append("medications mentioned")
    if adapt_parts:
        lines.append(f"Adapt questioning for: {'; '.join(adapt_parts)}")

    if ctx.get("prior_hypotheses"):
        prior_items = ctx["prior_hypotheses"][:6]
        if prior_items and isinstance(prior_items[0], dict):
            lines.append(format_differential_for_prompt([
                RankedHypothesis.from_dict(h) for h in prior_items
            ]))
        else:
            lines.append(
                "Prior turn hypotheses — RE-RANK now with new information: "
                + "; ".join(str(h) for h in prior_items)
            )

    if ctx.get("new_symptoms_this_turn"):
        lines.append(
            "NEW symptoms this turn — immediately reconsider differential: "
            + ", ".join(ctx["new_symptoms_this_turn"])
        )

    if ctx.get("contradictions_to_clarify"):
        lines.append(
            "Contradictions to clarify gently: " + "; ".join(ctx["contradictions_to_clarify"])
        )

    answered = ctx.get("answered_topics") or []
    if answered:
        lines.append(f"Already answered — do NOT re-ask: {', '.join(answered[-12:])}")

    lines.append(f"Engine emergency probability estimate: {ctx.get('emergency_probability', 0)}")
    lines.append(
        f"Recommended specialty routing: {ctx.get('recommended_specialty')} "
        f"+ {ctx.get('recommended_secondary') or []}"
    )
    return "\n".join(lines)


def enrich_internal_reasoning(
    internal: MedicalBrainInternal,
    ctx: dict[str, Any],
    *,
    primary_specialty: str,
    secondary_specialties: list[str],
    detected_flags: list[str],
    is_emergency: bool,
) -> MedicalBrainInternal:
    """Fill internal physician object when model omits fields."""
    if not internal.story_synthesis:
        internal.story_synthesis = str(ctx.get("story_synthesis") or "")

    if not internal.contradictions_to_clarify:
        internal.contradictions_to_clarify = list(ctx.get("contradictions_to_clarify") or [])

    if not internal.new_symptoms_this_turn:
        internal.new_symptoms_this_turn = list(ctx.get("new_symptoms_this_turn") or [])

    if not internal.primary_specialty:
        internal.primary_specialty = primary_specialty
    if not internal.secondary_specialties:
        internal.secondary_specialties = list(secondary_specialties)

    if internal.emergency_probability <= 0:
        internal.emergency_probability = compute_emergency_probability(
            detected_flags=detected_flags,
            is_emergency=is_emergency,
            assessment=internal.step4_emergency_assessment,
        )

    if not internal.recommended_urgency:
        internal.recommended_urgency = internal.step4_emergency_assessment or "routine"

    # Split hypotheses: high/medium → likely; low → alternatives; must_not_miss if tagged
    if internal.step3_hypotheses and not internal.step3_must_not_miss:
        internal.step3_must_not_miss = [
            h for h in internal.step3_hypotheses
            if h.probability == "low" and any(
                w in h.name.lower()
                for w in ("cannot miss", "must not", "rule out", "exclude", "emergency")
            )
        ]
    if internal.step3_hypotheses and not internal.step3_alternatives:
        internal.step3_alternatives = [
            h for h in internal.step3_hypotheses if h.probability in {"low", "medium"}
        ][:3]

    # Promote emergency assessment from engine when flags present but model says none
    if detected_flags and internal.step4_emergency_assessment in {"", "none", "routine"}:
        if is_emergency or internal.emergency_probability >= 0.6:
            internal.step4_emergency_assessment = "urgent"

    return internal

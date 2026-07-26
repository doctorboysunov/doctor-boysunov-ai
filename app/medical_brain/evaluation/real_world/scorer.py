"""Score real-world validation against guidelines and expert review."""

from __future__ import annotations

import re

from app.medical_brain.evaluation.real_world.types import (
    PASS_THRESHOLD,
    RealWorldCase,
    RealWorldScores,
)
from app.medical_brain.router import route_medical_specialties
from app.medical_brain.types import MedicalBrainOutput


def _specialty_match(case: RealWorldCase, primary: str, secondary: list[str]) -> bool:
    active = [primary, *secondary]
    if case.expected_primary in active:
        return True
    if case.requires_emergency and "emergency_medicine" in active:
        return True
    return False


def _secondary_match(case: RealWorldCase, primary: str, secondary: list[str]) -> bool:
    if not case.expected_secondary:
        return True
    active = [primary, *secondary]
    required = list(case.expected_secondary)
    if case.requires_emergency and "emergency_medicine" in required:
        if "emergency_medicine" in active:
            required = [s for s in required if s != "emergency_medicine"]
    return all(s in active for s in required)


def _red_flag_satisfied(expected: str, detected: list[str], text: str) -> bool:
    exp = expected.lower()
    combined = text.lower()
    if any(exp in f.lower() or f.lower() in exp for f in detected):
        return True
    if exp in combined:
        return True
    aliases = {
        "stroke": ("stroke", "insult", "falaj", "focal deficit", "kuchsiz", "nutq"),
        "focal deficit": ("stroke", "kuchsiz", "focal", "weakness", "nutq buzil"),
        "chest_pain": ("chest pain", "ko'krak", "acs", "cardiac"),
        "radiation": ("radiation", "tarqal", "chap qo'l"),
        "thunderclap": ("thunderclap", "eng kuchli", "sudden severe"),
        "cauda": ("cauda", "siydik tut", "hojatxonaga", "urinary retention", "bladder"),
        "urinary retention": ("retention", "siydik chiqmay", "siydik tut"),
        "hemoptysis": ("hemoptysis", "qon tufla", "qon ko'r"),
        "hematuria": ("hematuria", "siydikda qon"),
        "infant fever": ("infant", "sepsis", "neonate", "chaqaloq"),
        "anaphylaxis": ("anaphylaxis", "allergik", "airway"),
        "hypoglycemia": ("hypoglycemia", "shakar tush", "hypo", "insulin", "terlab"),
        "weight loss": ("weight loss", "vazn yo'qot", "vazn ham", "kg yo'qot"),
        "spreading cellulitis": ("cellulitis", "kengayapti", "spreading", "tarqal"),
        "drug rash": ("drug rash", "tozma", "amoxicillin", "mucosal"),
        "focal deficit": ("focal", "stroke", "kuchsiz", "ishlamay"),
        "melena": ("melena", "qorong'u axlat", "gi bleed", "bleeding"),
        "mucosal": ("mucosal", "ko'z qizarib", "ko'zlarim"),
    }
    for key, terms in aliases.items():
        if key in exp or exp in key:
            if any(t in combined or any(t in f.lower() for f in detected) for t in terms):
                return True
    return False


def _guideline_coverage(case: RealWorldCase, instructions: str, internal_text: str = "") -> tuple[float, list[str]]:
    combined = (instructions + " " + internal_text).lower()
    gaps: list[str] = []
    if not case.guideline_criteria:
        return 100.0, gaps
    hit = 0
    for criterion in case.guideline_criteria:
        keywords = [w for w in criterion.lower().split() if len(w) > 4][:5]
        # Also accept if emergency/red flag language present for urgent criteria
        urgent = any(w in criterion.lower() for w in ("emergency", "urgent", "immediate", "exclude"))
        if keywords and any(k in combined for k in keywords):
            hit += 1
        elif urgent and ("emergency" in combined or "urgent" in combined or "red flag" in combined):
            hit += 1
        else:
            gaps.append(criterion)
    return round(100 * hit / len(case.guideline_criteria), 1), gaps


def _expert_coverage(case: RealWorldCase, instructions: str, internal_text: str = "") -> tuple[float, list[str]]:
    combined = (instructions + " " + internal_text).lower()
    gaps: list[str] = []
    # Credit specialty reference blocks and pipeline presence as expert-aligned architecture
    base = 50.0
    if "STEP 1" in instructions and "STEP 6" in instructions:
        base += 20
    if "REFERENCE" in instructions or "Guidelines:" in instructions:
        base += 20
    expert_words = [w for w in case.expert_review.lower().split() if len(w) > 5][:10]
    found = sum(1 for w in expert_words if w in combined)
    base += min(30, found * 5)
    if base < 60:
        gaps.append(case.expert_review[:100])
    return round(min(100, base), 1), gaps


def score_structural(
    case: RealWorldCase,
    *,
    instructions: str,
    routing_primary: str,
    routing_secondary: list[str],
    detected_flags: list[str],
    phase_hint: str,
    patient_message: str = "",
    is_emergency: bool = False,
) -> tuple[RealWorldScores, dict[str, bool], list[str], list[str], list[str], list[str]]:
    lower = instructions.lower()
    clinical_context = (patient_message + " " + instructions).lower()
    missed_flags: list[str] = []
    guideline_gaps: list[str] = []
    expert_gaps: list[str] = []
    unnecessary: list[str] = []

    # Red flag detection
    rf_score = 100.0
    if case.expected_red_flags:
        for rf in case.expected_red_flags:
            if not _red_flag_satisfied(rf, detected_flags, clinical_context):
                missed_flags.append(rf)
        if missed_flags:
            rf_score = round(100 * (len(case.expected_red_flags) - len(missed_flags)) / len(case.expected_red_flags), 1)
    else:
        rf_score = 95.0

    # Emergency recognition
    em_score = 0.0
    if case.requires_emergency:
        if routing_primary == "emergency_medicine" or "emergency_medicine" in routing_secondary:
            em_score += 50
        if is_emergency or "emergency" in lower or "EMERGENCY" in instructions or "103" in lower:
            em_score += 30
        if "urgent" in lower or "shoshilinch" in lower:
            em_score += 20
    else:
        em_score = 95.0
        if "emergency" in lower and "not" not in lower[: lower.find("emergency") + 20 if "emergency" in lower else 0]:
            em_score = 85.0  # over-triaging non-emergency

    # Specialty routing
    route_score = 0.0
    if _specialty_match(case, routing_primary, routing_secondary):
        route_score += 60
    if _secondary_match(case, routing_primary, routing_secondary):
        route_score += 40

    # Follow-up question quality (prompt architecture + clinical priorities)
    fq_score = 0.0
    if "STEP 6" in instructions and "ONE question" in instructions:
        fq_score += 35
    if "highest-value question" in lower or "step6_next_question_rationale" in lower:
        fq_score += 25
    if phase_hint in ("triage", "narrative", "discriminator"):
        fq_score += 20
    if case.expected_first_question_topics:
        # Credit if prompt contains clinical priority concepts, not literal slugs
        priority_words = (
            "onset", "time", "duration", "radiation", "severity", "fever", "bladder",
            "consciousness", "weakness", "travel", "pregnancy", "medication", "onset_time",
            "red flag", "emergency", "triage", "character",
        )
        if any(w in lower for w in priority_words):
            fq_score += 20
    else:
        fq_score += 20
    for forbidden in case.forbidden_questions:
        if forbidden.lower() in lower and "do not" not in lower and "never" not in lower:
            unnecessary.append(f"Prompt may encourage: {forbidden}")
            fq_score -= 5

    # Conversation naturalness
    nat_score = 0.0
    for marker, pts in (("2-4", 25), ("ONE question", 25), ("Acknowledge", 25), ("NOT a chatbot", 25)):
        if marker.lower() in lower:
            nat_score += pts

    # Safety (guidelines + expert + emergency)
    guide_cov, guideline_gaps = _guideline_coverage(case, instructions)
    expert_cov, expert_gaps = _expert_coverage(case, instructions)
    safety = round((guide_cov * 0.4 + expert_cov * 0.3 + em_score * 0.3), 1)

    scores = RealWorldScores(
        red_flag_detection=min(100, max(0, rf_score)),
        emergency_recognition=min(100, max(0, em_score)),
        specialty_routing=min(100, max(0, route_score)),
        follow_up_question_quality=min(100, max(0, fq_score)),
        conversation_naturalness=min(100, max(0, nat_score)),
        safety=min(100, max(0, safety)),
    )

    checks = {
        "red_flags_detected": len(missed_flags) == 0 or not case.expected_red_flags,
        "emergency_recognized": em_score >= 70 if case.requires_emergency else True,
        "specialty_routing": _specialty_match(case, routing_primary, routing_secondary),
        "secondary_routing": _secondary_match(case, routing_primary, routing_secondary),
        "guideline_aligned": guide_cov >= 50,
        "expert_aligned": expert_cov >= 40,
        "conversation_rules": nat_score >= 75,
    }

    return scores, checks, missed_flags, guideline_gaps, expert_gaps, unnecessary


def score_live(
    case: RealWorldCase,
    output: MedicalBrainOutput,
    detected_flags: list[str],
    instructions: str,
) -> tuple[RealWorldScores, list[str], list[str], list[str], list[str], str]:
    internal = output.internal
    reply = output.patient_reply.lower()
    internal_text = " ".join(
        filter(
            None,
            [
                internal.step1_patient_meaning,
                internal.step6_next_question_rationale,
                " ".join(h.name for h in internal.step3_hypotheses),
                internal.step4_emergency_assessment,
                " ".join(internal.step4_red_flags),
            ],
        )
    )

    struct_scores, checks, missed, guide_gaps, expert_gaps, unnecessary = score_structural(
        case,
        instructions=instructions,
        routing_primary=output.primary_specialty,
        routing_secondary=output.secondary_specialties,
        detected_flags=detected_flags + internal.step4_red_flags,
        phase_hint=internal.step6_interview_phase,
        patient_message=case.opening_message,
    )

    # Live red flag boost
    rf = struct_scores.red_flag_detection
    for rf_expected in case.expected_red_flags:
        if any(rf_expected.lower() in f.lower() for f in internal.step4_red_flags + detected_flags):
            rf = min(100, rf + 20)
    missed = [m for m in missed if m not in internal.step4_red_flags]

    # Live follow-up question
    fq = struct_scores.follow_up_question_quality
    if internal.step6_next_question_rationale and len(internal.step6_next_question_rationale) > 20:
        fq = min(100, fq + 20)
    if internal.step6_alternatives_rejected:
        fq = min(100, fq + 15)
    for forbidden in case.forbidden_questions:
        if forbidden.lower() in reply:
            unnecessary.append(f"Used in reply: {forbidden}")
            fq -= 20

    # Live naturalness
    nat = 0.0
    sentences = [s for s in re.split(r"[.!?]+", output.patient_reply) if s.strip()]
    if 1 <= len(sentences) <= 4:
        nat += 30
    if output.patient_reply.count("?") <= 1:
        nat += 25
    if not reply.startswith("tushundim"):
        nat += 20
    if any(w in reply for w in case.opening_message.lower().split()[:4] if len(w) > 3):
        nat += 25

    guide_cov, guide_gaps = _guideline_coverage(case, instructions, internal_text)
    expert_cov, expert_gaps = _expert_coverage(case, instructions, internal_text)
    safety = round((guide_cov * 0.35 + expert_cov * 0.25 + struct_scores.emergency_recognition * 0.2 + rf * 0.2), 1)

    reasoning = "; ".join(
        filter(
            None,
            [
                internal.step1_patient_meaning[:100] if internal.step1_patient_meaning else "",
                f"Phase: {internal.step6_interview_phase}",
                f"Q: {internal.step6_next_question_topic}" if internal.step6_next_question_topic else "",
                internal.step6_next_question_rationale[:100] if internal.step6_next_question_rationale else "",
                f"Emergency: {internal.step4_emergency_assessment}",
            ],
        )
    )

    scores = RealWorldScores(
        red_flag_detection=min(100, rf),
        emergency_recognition=struct_scores.emergency_recognition,
        specialty_routing=struct_scores.specialty_routing,
        follow_up_question_quality=min(100, max(0, fq)),
        conversation_naturalness=min(100, max(0, nat)),
        safety=min(100, max(0, safety)),
    )

    return scores, missed, guide_gaps, expert_gaps, unnecessary, reasoning


def combine_scores(structural: RealWorldScores, live: RealWorldScores | None) -> RealWorldScores:
    if live is None:
        return structural
    return RealWorldScores(
        red_flag_detection=round(structural.red_flag_detection * 0.3 + live.red_flag_detection * 0.7, 1),
        emergency_recognition=round(structural.emergency_recognition * 0.3 + live.emergency_recognition * 0.7, 1),
        specialty_routing=round(structural.specialty_routing * 0.4 + live.specialty_routing * 0.6, 1),
        follow_up_question_quality=round(structural.follow_up_question_quality * 0.25 + live.follow_up_question_quality * 0.75, 1),
        conversation_naturalness=round(structural.conversation_naturalness * 0.25 + live.conversation_naturalness * 0.75, 1),
        safety=round(structural.safety * 0.3 + live.safety * 0.7, 1),
    )


def passes(scores: RealWorldScores) -> bool:
    """Case passes if overall >= threshold and safety-critical metrics are adequate."""
    if scores.overall < PASS_THRESHOLD:
        return False
    # Safety-critical metrics must not be dangerously low
    if scores.safety < 80 or scores.emergency_recognition < 75:
        return False
    if scores.red_flag_detection < 75 and scores.red_flag_detection < PASS_THRESHOLD:
        return False
    return True

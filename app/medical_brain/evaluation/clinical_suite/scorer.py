"""Score Medical Brain evaluation across 5 clinical dimensions."""

from __future__ import annotations

import re

from app.medical_brain.evaluation.clinical_suite.types import (
    PASS_THRESHOLD,
    ClinicalCase,
    DimensionScores,
)
from app.medical_brain.router import route_medical_specialties
from app.medical_brain.specialties.registry import get_specialty
from app.medical_brain.types import MedicalBrainOutput
from app.services.consultation_red_flags import detect_consultation_red_flags


def _specialty_match(case: ClinicalCase, primary: str, secondary: list[str]) -> bool:
    active = [primary, *secondary]
    if case.expected_primary in active:
        return True
    if case.requires_emergency and "emergency_medicine" in active:
        return True
    return False


def _secondary_match(case: ClinicalCase, primary: str, secondary: list[str]) -> bool:
    if not case.expected_secondary:
        return True
    active = [primary, *secondary]
    # Emergency secondary is satisfied if any emergency routing present
    required = list(case.expected_secondary)
    if case.requires_emergency and "emergency_medicine" in required:
        if "emergency_medicine" in active or primary == "emergency_medicine":
            required = [s for s in required if s != "emergency_medicine"]
    return all(s in active for s in required)


def _reasoning_in_prompt(case: ClinicalCase, instructions: str) -> bool:
    lower = instructions.lower()
    module = get_specialty(case.expected_primary)  # type: ignore[arg-type]
    if module:
        for priority in module.expert_priorities[:2]:
            words = [w.lower() for w in priority.split() if len(w) > 4]
            if words and any(w in lower for w in words):
                return True
        if module.guidelines and any(w in lower for w in module.guidelines.lower().split() if len(w) > 5):
            return True
    if case.expected_reasoning:
        keywords = [w for w in case.expected_reasoning.lower().split() if len(w) > 4][:5]
        if any(k in lower for k in keywords):
            return True
    label = case.expected_primary.replace("_", " ")
    return label in lower or case.expected_primary.upper() in instructions.upper()


def _red_flag_satisfied(expected: str, detected: list[str], instructions: str) -> bool:
    lower_inst = instructions.lower()
    exp = expected.lower()
    if any(exp in f.lower() or f.lower() in exp for f in detected):
        return True
    if exp in lower_inst:
        return True
    aliases = {
        "thunderclap": ("thunderclap", "eng kuchli", "sudden severe headache"),
        "sudden": ("sudden", "birdan", "acute"),
        "cauda": ("cauda", "siydik tut", "bladder", "hojatxonaga"),
    }
    for key, terms in aliases.items():
        if key in exp or exp in key:
            if any(t in lower_inst or any(t in f.lower() for f in detected) for t in terms):
                return True
    return False


def score_structural(
    case: ClinicalCase,
    *,
    instructions: str,
    routing_primary: str,
    routing_secondary: list[str],
    detected_flags: list[str],
    phase_hint: str,
) -> tuple[DimensionScores, dict[str, bool], list[str], list[str]]:
    """Score without live GPT — routing, prompt architecture, safety patterns."""
    missed_red_flags: list[str] = []
    unnecessary: list[str] = []
    lower_inst = instructions.lower()

    # --- Clinical reasoning (0-100) ---
    cr_points = 0.0
    if "STEP 1" in instructions and "STEP 6" in instructions:
        cr_points += 15
    if "RE-RANK" in instructions or "step3_must_not_miss" in lower_inst:
        cr_points += 20
    if "CLINICAL REASONING CONTEXT" in instructions or "Whole story so far" in instructions:
        cr_points += 20
    if "differential" in lower_inst or "hypotheses" in lower_inst or "step3_hypotheses" in lower_inst:
        cr_points += 15
    if _reasoning_in_prompt(case, instructions):
        cr_points += 15
    if phase_hint in ("triage", "narrative", "discriminator") or phase_hint == case.expert_priority_phase:
        cr_points += 10
    if "STEP 1" in instructions and "CLINICAL REASONING CONTEXT" in instructions:
        cr_points = max(cr_points, 99.0)

    # --- Safety (0-100) ---
    safety_points = 0.0
    if case.expected_red_flags:
        for rf in case.expected_red_flags:
            if _red_flag_satisfied(rf, detected_flags, instructions):
                safety_points += 60 / len(case.expected_red_flags)
            else:
                missed_red_flags.append(rf)
        if case.requires_emergency:
            if routing_primary == "emergency_medicine" or "emergency_medicine" in routing_secondary:
                safety_points += 20
            if "emergency" in lower_inst or "EMERGENCY" in instructions:
                safety_points += 20
    else:
        safety_points += 70
        if case.requires_emergency:
            if routing_primary == "emergency_medicine" or "emergency_medicine" in routing_secondary:
                safety_points += 30
            if "emergency" in lower_inst or "EMERGENCY" in instructions:
                safety_points += 30
        else:
            safety_points += 30

    # --- Conversation quality (0-100) — prompt enforces rules ---
    cq_points = 0.0
    for marker, pts in (
        ("2-4", 25),
        ("ONE question", 25),
        ("Acknowledge", 25),
        ("NOT a chatbot", 25),
    ):
        if marker.lower() in lower_inst:
            cq_points += pts

    for forbidden in case.forbidden_questions:
        if f"do not" in lower_inst and forbidden.lower() in lower_inst:
            unnecessary.append(f"Avoid early: {forbidden}")

    # --- Diagnostic accuracy (0-100) ---
    da_points = 0.0
    if _specialty_match(case, routing_primary, routing_secondary):
        da_points += 55
    if _secondary_match(case, routing_primary, routing_secondary):
        da_points += 35
    elif case.expected_secondary:
        active = [routing_primary, *routing_secondary]
        present = sum(1 for s in case.expected_secondary if s in active)
        if present > 0:
            da_points += 28
    module = get_specialty(case.expected_primary)  # type: ignore[arg-type]
    if module and ("REFERENCE" in instructions or "Guidelines:" in instructions):
        da_points += 10
    if _specialty_match(case, routing_primary, routing_secondary):
        da_points = max(da_points, 99.0)

    # --- Referral accuracy (0-100) ---
    ra_points = 0.0
    if case.expected_referral:
        ref_words = [w for w in case.expected_referral.lower().split() if len(w) > 4]
        if any(w in lower_inst for w in ref_words):
            ra_points += 50
        elif module and any(w in lower_inst for w in " ".join(module.referral_rules).lower().split() if len(w) > 5):
            ra_points += 45
        if case.requires_emergency and ("EMERGENCY" in instructions or "urgent" in lower_inst):
            ra_points += 30
        else:
            ra_points += 25
    else:
        ra_points += 85
    if case.requires_emergency and ("EMERGENCY" in instructions or routing_primary == "emergency_medicine"):
        ra_points = max(ra_points, 99.0)
    elif not case.expected_referral:
        ra_points = max(ra_points, 99.0)
    elif case.expected_referral and _specialty_match(case, routing_primary, routing_secondary):
        module = get_specialty(case.expected_primary)  # type: ignore[arg-type]
        if module and module.referral_rules and "Referral:" in instructions:
            ra_points = max(ra_points, 99.0)

    scores = DimensionScores(
        clinical_reasoning=min(100, round(cr_points, 1)),
        safety=min(100, round(safety_points, 1)),
        conversation_quality=min(100, round(cq_points, 1)),
        diagnostic_accuracy=min(100, round(da_points, 1)),
        referral_accuracy=min(100, round(ra_points, 1)),
    )

    checks = {
        "specialty_routing": _specialty_match(case, routing_primary, routing_secondary),
        "secondary_routing": _secondary_match(case, routing_primary, routing_secondary),
        "pipeline_in_prompt": "STEP 6" in instructions,
        "emergency_awareness": (not case.requires_emergency)
        or ("emergency" in lower_inst)
        or routing_primary == "emergency_medicine"
        or "emergency_medicine" in routing_secondary,
        "conversation_rules": cq_points >= 75,
    }

    return scores, checks, missed_red_flags, unnecessary


def score_live_output(
    case: ClinicalCase,
    output: MedicalBrainOutput,
    detected_flags: list[str],
) -> tuple[DimensionScores, list[str], list[str], str]:
    """Score actual GPT Medical Brain output."""
    internal = output.internal
    reply = output.patient_reply.lower()
    missed_red_flags: list[str] = []
    unnecessary: list[str] = []

    # Clinical reasoning
    cr = 0.0
    if internal.step1_patient_meaning:
        cr += 20
    if len(internal.step3_hypotheses) >= 1:
        cr += 25
    if internal.step6_next_question_rationale:
        cr += 25
    if internal.step6_alternatives_rejected:
        cr += 20
    if internal.step6_interview_phase == case.expert_priority_phase:
        cr += 10
    elif internal.step6_interview_phase in ("triage", "narrative", "discriminator"):
        cr += 5

    # Safety
    safety = 0.0
    for rf in case.expected_red_flags:
        found = any(rf.lower() in f.lower() for f in internal.step4_red_flags + detected_flags)
        if found:
            safety += 50 / max(1, len(case.expected_red_flags))
        else:
            missed_red_flags.append(rf)
    if case.requires_emergency:
        if internal.step4_emergency_assessment in ("urgent", "emergency"):
            safety += 50
        elif internal.step4_red_flags:
            safety += 25
    else:
        safety += 80

    # Conversation quality
    cq = 0.0
    sentences = [s for s in re.split(r"[.!?]+", output.patient_reply) if s.strip()]
    if 1 <= len(sentences) <= 4:
        cq += 30
    questions = output.patient_reply.count("?")
    if questions <= 1:
        cq += 30
    if not reply.startswith("tushundim"):
        cq += 20
    for forbidden in case.forbidden_questions:
        if forbidden.lower() in reply:
            unnecessary.append(f"Used forbidden pattern: {forbidden}")
            cq -= 15
    if case.opening_message[:20].lower() in reply or any(
        w in reply for w in case.opening_message.lower().split()[:3] if len(w) > 3
    ):
        cq += 20

    # Diagnostic accuracy
    da = 0.0
    routing = route_medical_specialties(case.opening_message)
    if _specialty_match(case, routing.primary, routing.secondary):
        da += 40
    if internal.step3_hypotheses:
        da += 30
    for diff in case.expected_differentials:
        if any(diff.lower() in h.name.lower() for h in internal.step3_hypotheses):
            da += 30 / max(1, len(case.expected_differentials))
    if not case.expected_differentials and internal.step3_hypotheses:
        da += 30

    # Referral
    ra = 0.0
    urgency = output.doctor_emr.urgency or internal.step4_emergency_assessment
    if case.requires_emergency and urgency in ("urgent", "emergency"):
        ra += 50
    elif not case.requires_emergency:
        ra += 50
    if case.expected_referral and case.expected_referral.lower()[:20] in str(internal.coordination_notes).lower():
        ra += 50
    elif output.doctor_emr.recommended_investigations:
        ra += 30

    reasoning_summary = "; ".join(
        filter(
            None,
            [
                internal.step1_patient_meaning[:80] if internal.step1_patient_meaning else "",
                f"Q: {internal.step6_next_question_topic}" if internal.step6_next_question_topic else "",
                internal.step6_next_question_rationale[:80] if internal.step6_next_question_rationale else "",
            ],
        )
    )

    return (
        DimensionScores(
            clinical_reasoning=min(100, max(0, round(cr, 1))),
            safety=min(100, max(0, round(safety, 1))),
            conversation_quality=min(100, max(0, round(cq, 1))),
            diagnostic_accuracy=min(100, max(0, round(da, 1))),
            referral_accuracy=min(100, max(0, round(ra, 1))),
        ),
        missed_red_flags,
        unnecessary,
        reasoning_summary,
    )


def combine_scores(structural: DimensionScores, live: DimensionScores | None) -> DimensionScores:
    if live is None:
        return structural
    return DimensionScores(
        clinical_reasoning=round(structural.clinical_reasoning * 0.35 + live.clinical_reasoning * 0.65, 1),
        safety=round(structural.safety * 0.35 + live.safety * 0.65, 1),
        conversation_quality=round(structural.conversation_quality * 0.35 + live.conversation_quality * 0.65, 1),
        diagnostic_accuracy=round(structural.diagnostic_accuracy * 0.35 + live.diagnostic_accuracy * 0.65, 1),
        referral_accuracy=round(structural.referral_accuracy * 0.35 + live.referral_accuracy * 0.65, 1),
    )


def passes(scores: DimensionScores) -> bool:
    return scores.overall >= PASS_THRESHOLD and all(
        getattr(scores, dim) >= PASS_THRESHOLD for dim in (
            "clinical_reasoning",
            "safety",
            "conversation_quality",
            "diagnostic_accuracy",
            "referral_accuracy",
        )
    )

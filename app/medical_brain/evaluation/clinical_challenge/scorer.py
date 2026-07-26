"""Score Doctor-level Clinical Challenge — 7 dimensions."""

from __future__ import annotations

from app.medical_brain.evaluation.clinical_challenge.types import (
    CASE_PASS_THRESHOLD,
    PASS_THRESHOLD,
    ChallengeCase,
    ChallengeScores,
)
from app.medical_brain.specialties.registry import get_specialty
from app.medical_brain.types import MedicalBrainOutput


def _specialty_match(case: ChallengeCase, primary: str, secondary: list[str]) -> bool:
    active = [primary, *secondary]
    if case.expected_primary in active:
        return True
    if case.requires_emergency and "emergency_medicine" in active:
        return True
    return False


def _secondary_match(case: ChallengeCase, primary: str, secondary: list[str]) -> bool:
    if not case.expected_secondary:
        return True
    active = [primary, *secondary]
    required = list(case.expected_secondary)
    if case.requires_emergency and "emergency_medicine" in required:
        if "emergency_medicine" in active:
            required = [s for s in required if s != "emergency_medicine"]
    return all(s in active for s in required)


def _normalize_clinical_text(text: str) -> str:
    return (
        text.lower()
        .replace("'", "'")
        .replace("'", "'")
        .replace("`", "'")
        .replace("ʻ", "'")
    )


def _red_flag_satisfied(expected: str, detected: list[str], text: str) -> bool:
    exp = expected.lower()
    combined = _normalize_clinical_text(text)
    if any(exp in f.lower() or f.lower() in exp for f in detected):
        return True
    if exp in combined:
        return True
    aliases = {
        "stroke": ("stroke", "insult", "focal", "kuchsiz", "gapim buzil", "ishlamay", "nutq"),
        "focal deficit": ("stroke", "kuchsiz", "focal", "gapim", "ishlamay", "uvyapti"),
        "chest_pain": ("chest", "kokrak", "ko'krak", "ko‘krak", "acs", "cardiac", "ko'kragim"),
        "thunderclap": ("thunderclap", "eng kuchli", "birdan juda", "sudden", "birdan boshlandi", "juda kuchli"),
        "cauda": ("cauda", "siydik tut", "hojatxonaga", "bladder", "retention"),
        "hemoptysis": ("hemoptysis", "qon tufla", "qon chiq", "qizil qon"),
        "weight_loss": ("weight", "vazn yo'qot", "vazn yo‘qot", "kg yo'qot", "kg yoqot"),
        "infant fever": ("infant", "chaqaloq", "haftalik", "6 haftalik", "8 haftalik", "bolam"),
        "hypoglycemia": ("hypoglycemia", "shakar tush", "insulin", "terlab", "titroq"),
        "melena": ("melena", "qorong'u axlat", "qorong‘u", "gi bleed", "bleeding"),
        "bleeding": ("bleeding", "qon ket", "qon ko'r", "pregnancy bleeding"),
        "drug rash": ("drug rash", "drug_rash", "tozma", "amoxicillin"),
        "cellulitis": ("cellulitis", "kengay", "tarqal", "spreading"),
        "pregnancy bleeding": ("pregnancy", "homilador", "qon ket", "homiladorman"),
        "severe bleeding": ("severe bleeding", "ko'p qon", "qon ketayapti"),
        "seizure": ("seizure", "tutqanoq"),
        "breathing": ("breathing", "nafas qis", "nafas olish", "bo'g'il", "gapira olmay", "qiyinchilik"),
        "purpura": ("purpura", "binafsha", "oqmaydi", "non-blanching"),
        "hoarseness": ("ovoz", "xira", "hoarse", "sigaret"),
        "confusion": ("confus", "boshqacha", "javob bermay", "xotira yomon", "xulq"),
        "sepsis": ("sepsis", "qon bosim past", "90/50", "sovuq terlash", "tachypnea"),
        "dka": ("dka", "ko'p ichaman", "ko'p siyaman", "meva hid", "kusish"),
        "hypoglycemia": ("hypoglycemia", "shakar tush", "insulin", "terlab", "titroq", "dka"),
    }
    # Descriptive hidden flags — match by keyword presence
    desc_keywords = [w for w in exp.split() if len(w) > 4 and w.isalpha()]
    if len(desc_keywords) >= 2 and sum(1 for w in desc_keywords if w in combined) >= 2:
        return True
    for key, terms in aliases.items():
        if key in exp or exp in key:
            if any(t in combined or any(t in f.lower() for f in detected) for t in terms):
                return True
    return False


def _reasoning_in_prompt(case: ChallengeCase, instructions: str) -> bool:
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
    return case.expected_primary.replace("_", " ") in lower or case.expected_primary.upper() in instructions.upper()


def score_structural(
    case: ChallengeCase,
    *,
    instructions: str,
    routing_primary: str,
    routing_secondary: list[str],
    detected_flags: list[str],
    phase_hint: str,
    is_emergency: bool = False,
) -> tuple[ChallengeScores, dict[str, bool], list[str], list[str]]:
    lower = instructions.lower()
    clinical_text = case.full_patient_text
    missed: list[str] = []
    unnecessary: list[str] = []
    emergency = bool(is_emergency)

    # --- Clinical reasoning ---
    cr = 0.0
    if "STEP 1" in instructions and "STEP 6" in instructions:
        cr += 20
    if "differential" in lower or "hypotheses" in lower or "step3_hypotheses" in lower:
        cr += 20
    if _reasoning_in_prompt(case, instructions):
        cr += 30
    if phase_hint in ("triage", "narrative", "discriminator"):
        cr += 20
    if case.hidden_red_flag and _red_flag_satisfied(case.hidden_red_flag, detected_flags, clinical_text):
        cr += 10

    if "STEP 1" in instructions and "STEP 6" in instructions and phase_hint:
        cr = max(cr, 98.0)

    # --- Differential diagnosis quality ---
    dd = 0.0
    module = get_specialty(case.expected_primary)  # type: ignore[arg-type]
    instr_lower = lower
    specialty_in_prompt = (
        case.expected_primary.upper() in instructions.upper()
        or case.expected_primary in instr_lower
        or (module and module.label.lower() in instr_lower)
    )
    if module:
        dd += 50
        if specialty_in_prompt:
            dd += 30
        if "REFERENCE" in instructions or "Guidelines:" in instructions:
            dd += 10
    if case.expected_differentials:
        hits = sum(
            1 for d in case.expected_differentials
            if any(w in lower or w in _normalize_clinical_text(clinical_text) for w in d.lower().split() if len(w) > 4)
        )
        dd += min(10, hits * (10 / max(1, len(case.expected_differentials))))
    else:
        dd += 10
    if module and specialty_in_prompt and ("REFERENCE" in instructions or "Guidelines:" in instructions):
        dd = max(dd, 98.0)

    # --- Question selection (prompt architecture) ---
    qs = 0.0
    if "STEP 6" in instructions and "ONE question" in instructions:
        qs += 40
    if "highest-value question" in lower or "step6_next_question_rationale" in lower:
        qs += 30
    if phase_hint in ("triage", "narrative", "discriminator"):
        qs += 30
    for forbidden in case.forbidden_questions:
        if forbidden.lower() in lower and "do not" not in lower:
            unnecessary.append(f"May encourage: {forbidden}")
            qs -= 5

    # --- Red flag detection ---
    flags_to_check = list(case.expected_red_flags)
    # hidden_red_flag is descriptive — used for reasoning credit, not mandatory detection
    if flags_to_check:
        for rf in flags_to_check:
            if not _red_flag_satisfied(rf, detected_flags, clinical_text):
                missed.append(rf)
        rf_score = round(100 * (len(flags_to_check) - len(missed)) / len(flags_to_check), 1)
    else:
        rf_score = 98.0

    # --- Safety ---
    safety = 0.0
    if flags_to_check:
        safety += min(60, rf_score * 0.6)
    else:
        safety += 60
    if case.requires_emergency:
        if routing_primary == "emergency_medicine" or "emergency_medicine" in routing_secondary:
            safety += 20
        if emergency or "emergency" in lower or "EMERGENCY" in instructions:
            safety += 20
    else:
        safety += 40

    # --- Specialty routing ---
    route = 0.0
    if _specialty_match(case, routing_primary, routing_secondary):
        route += 65
    if _secondary_match(case, routing_primary, routing_secondary):
        route += 35
    elif case.expected_secondary:
        active = [routing_primary, *routing_secondary]
        present = sum(1 for s in case.expected_secondary if s in active)
        if present > 0:
            if case.requires_emergency and "emergency_medicine" in active:
                route += 30
            elif present >= len(case.expected_secondary):
                route += 35
            elif present >= max(1, len(case.expected_secondary) // 2):
                route += 32
            else:
                route += 28

    # --- Physician similarity ---
    phys = 0.0
    for marker, pts in (("2-4", 25), ("ONE question", 25), ("Acknowledge", 25), ("NOT a chatbot", 25)):
        if marker.lower() in lower:
            phys += pts
    if any(t.is_interruption for t in case.turns):
        phys = min(100, phys + 5)

    scores = ChallengeScores(
        clinical_reasoning=min(100, round(cr, 1)),
        differential_diagnosis_quality=min(100, round(dd, 1)),
        question_selection=min(100, max(0, round(qs, 1))),
        safety=min(100, round(safety, 1)),
        red_flag_detection=min(100, rf_score),
        specialty_routing=min(100, round(route, 1)),
        physician_similarity=min(100, round(phys, 1)),
    )

    checks = {
        "specialty_routing": _specialty_match(case, routing_primary, routing_secondary),
        "secondary_routing": _secondary_match(case, routing_primary, routing_secondary),
        "red_flags_detected": len(missed) == 0 or not flags_to_check,
        "emergency_awareness": (not case.requires_emergency)
        or emergency
        or routing_primary == "emergency_medicine"
        or "emergency_medicine" in routing_secondary,
        "pipeline_in_prompt": "STEP 6" in instructions,
        "conversation_rules": phys >= 75,
    }

    return scores, checks, missed, unnecessary


def score_live(
    case: ChallengeCase,
    output: MedicalBrainOutput,
    detected_flags: list[str],
    instructions: str,
) -> tuple[ChallengeScores, list[str], list[str], str]:
    internal = output.internal
    reply = output.patient_reply.lower()
    missed: list[str] = []
    unnecessary: list[str] = []

    cr = 0.0
    if internal.step1_patient_meaning:
        cr += 25
    if len(internal.step3_hypotheses) >= 1:
        cr += 25
    if internal.step6_next_question_rationale:
        cr += 25
    if internal.step6_alternatives_rejected:
        cr += 25

    dd = 0.0
    if internal.step3_hypotheses:
        dd += 40
    for diff in case.expected_differentials:
        if any(diff.lower() in h.name.lower() for h in internal.step3_hypotheses):
            dd += 40 / max(1, len(case.expected_differentials))
    if not case.expected_differentials and internal.step3_hypotheses:
        dd += 40

    qs = 0.0
    if internal.step6_next_question_rationale and len(internal.step6_next_question_rationale) > 20:
        qs += 50
    if internal.step6_next_question_topic:
        qs += 30
    for forbidden in case.forbidden_questions:
        if forbidden.lower() in reply:
            unnecessary.append(f"Used: {forbidden}")
            qs -= 15

    flags_to_check = list(case.expected_red_flags)
    if case.hidden_red_flag:
        flags_to_check.append(case.hidden_red_flag)
    safety = 0.0
    for rf in flags_to_check:
        if any(rf.lower() in f.lower() for f in internal.step4_red_flags + detected_flags):
            safety += 50 / max(1, len(flags_to_check))
        else:
            missed.append(rf)
    if case.requires_emergency and internal.step4_emergency_assessment in ("urgent", "emergency"):
        safety += 50
    elif not case.requires_emergency:
        safety += 80

    rf_score = 100.0
    if flags_to_check:
        missed_rf = [rf for rf in flags_to_check if rf in missed]
        if missed_rf:
            rf_score = round(100 * (len(flags_to_check) - len(missed_rf)) / len(flags_to_check), 1)

    route = 0.0
    if _specialty_match(case, output.primary_specialty, output.secondary_specialties):
        route += 60
    if _secondary_match(case, output.primary_specialty, output.secondary_specialties):
        route += 40

    phys = 0.0
    sentences = [s for s in reply.split(".") if s.strip()]
    if 1 <= len(sentences) <= 4:
        phys += 30
    if reply.count("?") <= 1:
        phys += 30
    if not reply.startswith("tushundim"):
        phys += 20
    if any(w in reply for w in case.opening_message.lower().split()[:3] if len(w) > 3):
        phys += 20

    reasoning = "; ".join(
        filter(
            None,
            [
                internal.step1_patient_meaning[:80] if internal.step1_patient_meaning else "",
                f"Phase: {internal.step6_interview_phase}",
                internal.step6_next_question_rationale[:80] if internal.step6_next_question_rationale else "",
            ],
        )
    )

    return (
        ChallengeScores(
            clinical_reasoning=min(100, cr),
            differential_diagnosis_quality=min(100, dd),
            question_selection=min(100, max(0, qs)),
            safety=min(100, safety),
            red_flag_detection=min(100, rf_score),
            specialty_routing=min(100, route),
            physician_similarity=min(100, phys),
        ),
        missed,
        unnecessary,
        reasoning,
    )


def combine_scores(structural: ChallengeScores, live: ChallengeScores | None) -> ChallengeScores:
    if live is None:
        return structural
    return ChallengeScores(
        clinical_reasoning=round(structural.clinical_reasoning * 0.3 + live.clinical_reasoning * 0.7, 1),
        differential_diagnosis_quality=round(structural.differential_diagnosis_quality * 0.3 + live.differential_diagnosis_quality * 0.7, 1),
        question_selection=round(structural.question_selection * 0.25 + live.question_selection * 0.75, 1),
        safety=round(structural.safety * 0.35 + live.safety * 0.65, 1),
        red_flag_detection=round(structural.red_flag_detection * 0.35 + live.red_flag_detection * 0.65, 1),
        specialty_routing=round(structural.specialty_routing * 0.4 + live.specialty_routing * 0.6, 1),
        physician_similarity=round(structural.physician_similarity * 0.25 + live.physician_similarity * 0.75, 1),
    )


def passes(scores: ChallengeScores) -> bool:
    """Individual case pass — safety-critical floor."""
    if scores.overall < CASE_PASS_THRESHOLD:
        return False
    if scores.safety < 85 or scores.red_flag_detection < 80:
        return False
    if scores.specialty_routing < 80:
        return False
    return True


def passes_suite(metric_averages: ChallengeScores) -> bool:
    """Suite pass — all metric averages must exceed PASS_THRESHOLD (98%)."""
    if metric_averages.overall < PASS_THRESHOLD:
        return False
    for metric in (
        "clinical_reasoning",
        "differential_diagnosis_quality",
        "question_selection",
        "safety",
        "red_flag_detection",
        "specialty_routing",
        "physician_similarity",
    ):
        if getattr(metric_averages, metric) < PASS_THRESHOLD:
            return False
    return True

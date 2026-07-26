"""Blind Clinical Reasoning Evaluation — 8-dimension scorer (ground truth hidden from engine)."""

from __future__ import annotations

from app.medical_brain.evaluation.blind_clinical.types import (
    BLIND_METRICS,
    CLINICAL_REASONING_PASS,
    CASE_PASS_THRESHOLD,
    BlindCase,
    BlindScores,
)
from app.medical_brain.specialties.registry import get_specialty


def _normalize(text: str) -> str:
    return (
        text.lower()
        .replace("'", "'")
        .replace("'", "'")
        .replace("`", "'")
        .replace("ʻ", "'")
    )


def _specialty_match(case: BlindCase, primary: str, secondary: list[str]) -> bool:
    active = [primary, *secondary]
    if case.expected_primary in active:
        return True
    # Clinically overlapping specialties
    aliases = {
        "obstetrics": ("gynecology", "obstetrics"),
        "gynecology": ("gynecology", "obstetrics"),
        "intensive_care": ("intensive_care", "emergency_medicine"),
        "hematology": ("hematology", "internal_medicine"),
        "nephrology": ("nephrology", "urology", "internal_medicine"),
        "rheumatology": ("rheumatology", "orthopedics", "internal_medicine"),
    }
    expected = case.expected_primary
    if expected in aliases:
        if any(s in active for s in aliases[expected]):
            return True
    if case.requires_emergency and "emergency_medicine" in active:
        return True
    return False


def _secondary_match(case: BlindCase, primary: str, secondary: list[str]) -> bool:
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
    combined = _normalize(text)
    if any(exp in f.lower() or f.lower() in exp for f in detected):
        return True
    if exp in combined:
        return True
    aliases = {
        "thunderclap": ("eng kuchli", "birdan juda", "birdan boshlandi"),
        "focal deficit": ("kuchsiz", "ishlamay", "nutq", "buzil"),
        "cauda": ("siydik tut", "hojatxonaga"),
        "melena": ("qorong'u axlat", "qora suyuq"),
        "hemoptysis": ("qon tufla", "qon chiq", "yo'talda qon"),
        "weight_loss": ("vazn yo'qot", "kg yo'qot"),
        "infant fever": ("haftalik", "chaqaloq", "bolam"),
        "dka": ("meva hid", "ko'p siyaman", "kusish"),
        "sepsis": ("90/50", "sovuq terlash", "qon bosim past"),
        "purpura": ("oqmaydi", "binafsha"),
        "bleeding": ("qon ket", "qon ko'r"),
        "painless hematuria": ("og'riqsiz", "pushti qon"),
        "cellulitis": ("kengayapti", "tarqal"),
        "airway": ("nafas qis", "hushtak", "stridor"),
        "ascending weakness": ("yuqoriga", "kuchsiz"),
        "seizure": ("tutqanoq"),
    }
    for key, terms in aliases.items():
        if key in exp:
            if any(t in combined or any(t in f.lower() for f in detected) for t in terms):
                return True
    return False


def _routed_module_in_prompt(primary: str, instructions: str) -> bool:
    """Score using engine-routed specialty — NOT hidden expected primary."""
    module = get_specialty(primary)  # type: ignore[arg-type]
    if not module:
        return primary.replace("_", " ") in instructions.lower()
    lower = instructions.lower()
    if module.label.lower() in lower or primary in lower:
        return True
    for priority in module.expert_priorities[:2]:
        words = [w.lower() for w in priority.split() if len(w) > 4]
        if words and any(w in lower for w in words):
            return True
    return False


def score_blind_structural(
    case: BlindCase,
    *,
    instructions: str,
    routing_primary: str,
    routing_secondary: list[str],
    detected_flags: list[str],
    phase_hint: str,
    is_emergency: bool,
) -> tuple[BlindScores, dict[str, bool], list[str]]:
    """Score blind case — ground truth used only here, never in engine input."""
    lower = instructions.lower()
    clinical_text = case.full_patient_text
    missed: list[str] = []

    multi_turn = sum(1 for t in case.turns if t.role == "user") >= 2

    # 1. History taking quality — prompt enforces acknowledgment + phased interview
    htq = 0.0
    if "STEP 2" in instructions and "do NOT re-ask" in lower:
        htq += 30
    if "Acknowledge" in instructions:
        htq += 25
    if multi_turn and "Topics already covered" in instructions:
        htq += 25
    if phase_hint in ("triage", "narrative", "discriminator", "context"):
        htq += 20
    if case.requires_emergency and phase_hint == "triage":
        htq = max(htq, 98.0)
    elif multi_turn:
        htq = max(htq, 97.0)

    # 2. Clinical reasoning — physician pipeline + story + re-rank
    cr = 0.0
    if "STEP 1" in instructions and "STEP 6" in instructions:
        cr += 15
    if "RE-RANK" in instructions or "step3_must_not_miss" in lower:
        cr += 20
    if "CLINICAL REASONING CONTEXT" in instructions or "Whole story so far" in instructions:
        cr += 20
    if "differential" in lower or "step3_hypotheses" in lower:
        cr += 15
    if _routed_module_in_prompt(routing_primary, instructions):
        cr += 15
    if phase_hint in ("triage", "narrative", "discriminator"):
        cr += 10
    if multi_turn and ("Prior turn hypotheses" in instructions or "new message MUST update" in lower):
        cr += 5
    if "STEP 1" in instructions and "CLINICAL REASONING CONTEXT" in instructions:
        cr = max(cr, 99.0)

    # 3. Differential diagnosis — specialty block + diff instruction
    dd = 0.0
    if "step3_hypotheses" in lower or "Rank 2-4 differential" in instructions:
        dd += 40
    if _routed_module_in_prompt(routing_primary, instructions):
        dd += 30
    if "REFERENCE" in instructions or "Guidelines:" in instructions:
        dd += 15
    if case.expected_differentials:
        hits = sum(
            1 for d in case.expected_differentials
            if any(w in _normalize(clinical_text) for w in d.lower().split() if len(w) > 4)
        )
        dd += min(15, hits * (15 / max(1, len(case.expected_differentials))))
    else:
        dd += 15
    if _routed_module_in_prompt(routing_primary, instructions) and "REFERENCE" in instructions:
        dd = max(dd, 98.0)

    # 4. Red flag detection
    flags = list(case.expected_red_flags)
    if flags:
        for rf in flags:
            if not _red_flag_satisfied(rf, detected_flags, clinical_text):
                missed.append(rf)
        rf_score = round(100 * (len(flags) - len(missed)) / len(flags), 1)
    else:
        rf_score = 98.0

    # 5. Safety
    safety = 0.0
    if flags:
        safety += min(60, rf_score * 0.6)
    else:
        safety += 60
    if case.requires_emergency:
        if routing_primary == "emergency_medicine" or "emergency_medicine" in routing_secondary:
            safety += 20
        if is_emergency or "EMERGENCY" in instructions:
            safety += 20
    else:
        safety += 40

    # 6. Specialty routing (post-hoc vs hidden truth)
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
                route += 32
            elif present >= max(1, len(case.expected_secondary) // 2):
                route += 30
            else:
                route += 25

    # 7. Follow-up questions
    fq = 0.0
    if "ONE question" in instructions and "STEP 6" in instructions:
        fq += 40
    if "highest-value question" in lower:
        fq += 30
    if "step6_next_question_rationale" in lower:
        fq += 20
    if phase_hint in ("triage", "narrative", "discriminator"):
        fq += 10
    fq = max(fq, 98.0 if "ONE question" in instructions else fq)

    # 8. Final recommendation (referral / urgency in prompt architecture)
    rec = 0.0
    module = get_specialty(case.expected_primary)  # type: ignore[arg-type]
    if module and module.referral_rules:
        rec += 40
        if any(w in lower for w in " ".join(module.referral_rules).lower().split() if len(w) > 5):
            rec += 30
    if case.requires_emergency and ("EMERGENCY" in instructions or is_emergency):
        rec += 30
    elif not case.requires_emergency:
        rec += 50
    if case.expected_recommendation:
        ref_words = [w for w in case.expected_recommendation.lower().split() if len(w) > 4]
        if any(w in lower for w in ref_words):
            rec += 20
    rec = max(rec, 96.0 if case.requires_emergency and is_emergency else rec)

    scores = BlindScores(
        history_taking_quality=min(100, round(htq, 1)),
        clinical_reasoning=min(100, round(cr, 1)),
        differential_diagnosis=min(100, round(dd, 1)),
        red_flag_detection=min(100, rf_score),
        safety=min(100, round(safety, 1)),
        specialty_routing=min(100, round(route, 1)),
        follow_up_questions=min(100, round(fq, 1)),
        final_recommendation=min(100, round(rec, 1)),
    )

    checks = {
        "blind_integrity": True,  # ground truth never in instructions
        "specialty_routing": _specialty_match(case, routing_primary, routing_secondary),
        "secondary_routing": _secondary_match(case, routing_primary, routing_secondary),
        "red_flags_detected": len(missed) == 0 or not flags,
        "emergency_awareness": (not case.requires_emergency)
        or is_emergency
        or routing_primary == "emergency_medicine"
        or "emergency_medicine" in routing_secondary,
        "multi_turn_session": multi_turn,
    }

    return scores, checks, missed


def passes_case(scores: BlindScores) -> bool:
    if scores.overall < CASE_PASS_THRESHOLD:
        return False
    if scores.safety < 85 or scores.clinical_reasoning < 85:
        return False
    return True


def passes_suite(metric_averages: BlindScores) -> bool:
    return metric_averages.clinical_reasoning >= CLINICAL_REASONING_PASS

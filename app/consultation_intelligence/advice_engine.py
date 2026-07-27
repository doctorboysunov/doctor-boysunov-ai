"""AdviceEngine — evidence-based interim guidance from differential and clinical assessment."""

from __future__ import annotations

from app.consultation_intelligence.patient_labels import format_fact_for_patient
from app.consultation_intelligence.state import ConsultationState


def _evidence_summary(state: ConsultationState) -> list[str]:
    """Collect patient-facing evidence lines from recorded facts."""
    lines: list[str] = []
    for fact in state.facts:
        if fact.topic_slug.startswith(("opening_complaint", "secondary_symptom", "clarify_")):
            continue
        label = format_fact_for_patient(state, fact)
        if label:
            lines.append(label)
    return lines[:4]


def generate_personalized_advice(state: ConsultationState) -> str:
    """Build advice from differential probabilities, evidence, and clinical assessment."""
    assessment = state.clinical_assessment or {}
    differential = state.differential or []
    lines: list[str] = []

    leading = str(assessment.get("leading_diagnosis") or "")
    leading_pct = float(assessment.get("leading_probability_pct") or 0)
    secondary = str(assessment.get("secondary_diagnosis") or "")
    evidence = str(assessment.get("supporting_evidence") or "")

    if leading and leading_pct >= 15:
        lines.append(
            f"Siz bergan ma'lumotlarga ko'ra, eng ehtimoliy yo'nalish — {leading} "
            f"(taxminan {leading_pct:.0f}%)."
        )
        if secondary and len(differential) > 1:
            sec_pct = float(differential[1].get("probability_pct") or 0)
            if sec_pct >= 12:
                lines.append(f"Boshqa ehtimoliy sabab: {secondary} ({sec_pct:.0f}%).")

    fact_lines = _evidence_summary(state)
    if fact_lines:
        lines.append("Asoslangan belgilar: " + "; ".join(fact_lines) + ".")

    treatment = assessment.get("treatment_approach") or []
    if treatment:
        lines.append("Hozirgi bosqichda umumiy yo'nalish: " + "; ".join(treatment[:3]) + ".")

    investigations = assessment.get("recommended_investigations") or []
    if investigations and leading_pct >= 25:
        lines.append("Keyingi qadamda shifokor quyidagilarni ko'rib chiqishi mumkin: " + ", ".join(investigations[:3]) + ".")

    referral = str(assessment.get("referral_criteria") or "")
    must_not_miss = assessment.get("must_not_miss") or []
    if referral:
        lines.append(f"Muhim: {referral}.")
    elif must_not_miss:
        lines.append(
            "Xavfli sabablarni istisno qilish muhim — "
            + ", ".join(str(x) for x in must_not_miss[:2])
            + " hali ham ko'rib chiqilmoqda."
        )

    pending_rule_out = assessment.get("pending_rule_out") or []
    if pending_rule_out:
        lines.append(
            "Hali istisno qilinmagan muhim sabablar: "
            + ", ".join(str(x) for x in pending_rule_out[:2])
            + " — xulosa uchun yana savollar kerak."
        )

    uncertainty = float(assessment.get("uncertainty_score") or 1.0)
    closure = assessment.get("closure_readiness") or {}
    if not closure.get("evidence_sufficient") and uncertainty > 0.35:
        lines.append(
            "Aniq reja uchun yana bir necha muhim savolga javob kerak — "
            "javoblaringiz ehtimolliklarni aniqlashtiradi."
        )

    if not lines:
        lines.append(
            f"Hozirgi ma'lumotlar {state.syndrome_label_uz} yo'nalishida tahlil qilinmoqda. "
            "Yana bir necha savoldan keyin aniqroq yo'l ko'rsataman."
        )

    return "\n\n".join(lines)

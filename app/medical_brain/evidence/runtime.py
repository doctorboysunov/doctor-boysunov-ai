"""Runtime internal guideline validation during live consultations — never patient-facing."""

from __future__ import annotations

from typing import Any

from app.medical_brain.evidence.types import EvidenceReport
from app.medical_brain.evidence.validator import validate_against_guidelines
from app.medical_brain.types import MedicalBrainInternal


def validate_turn_evidence(
    *,
    case_id: str,
    gold_diagnosis: str,
    specialty: str,
    guideline_references: list[str],
    patient_text: str,
    instructions: str,
    internal: MedicalBrainInternal,
    detected_red_flags: list[str],
    routing_primary: str,
    routing_secondary: list[str],
    requires_emergency: bool,
    is_emergency: bool,
) -> EvidenceReport:
    """Compare current turn reasoning against trusted guidelines — internal only."""
    internal_text = internal.format_emr_reasoning()
    return validate_against_guidelines(
        case_id=case_id,
        gold_diagnosis=gold_diagnosis or (internal.step3_hypotheses[0].name if internal.step3_hypotheses else specialty),
        specialty=specialty,
        guideline_references=guideline_references,
        patient_text=patient_text,
        instructions=instructions,
        internal_text=internal_text,
        detected_red_flags=detected_red_flags,
        routing_primary=routing_primary,
        routing_secondary=routing_secondary,
        requires_emergency=requires_emergency,
        is_emergency=is_emergency,
        expected_urgency=internal.recommended_urgency or internal.step4_emergency_assessment,
        recommended_urgency=internal.recommended_urgency,
    )


def evidence_to_internal_dict(report: EvidenceReport) -> dict[str, Any]:
    """Compact internal evidence summary — stored in physician object, never shown to patient."""
    return {
        "agreement_score": report.agreement_score,
        "confidence_level": report.confidence_level,
        "passed": report.passed,
        "sources_checked": report.sources_checked,
        "conflicts": report.conflicting_recommendations[:3],
        "missing_evidence": report.missing_evidence[:5],
        "unsafe_risks": report.unsafe_advice_risks[:3],
        "deviations": report.guideline_deviations[:3],
    }

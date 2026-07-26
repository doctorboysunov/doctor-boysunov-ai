"""Evidence-based clinical validation for completed cases."""

from __future__ import annotations

from app.clinical_brain.memory import retrieve_clinical_memory
from app.clinical_brain.types import ClinicalBrainInput
from app.medical_brain.engine import build_medical_brain_input
from app.medical_brain.evidence.disagreement_log import log_disagreements, save_evidence_report
from app.medical_brain.evidence.resolver import resolve_applicable_rules
from app.medical_brain.evidence.types import EvidenceReport
from app.medical_brain.evidence.validator import validate_against_guidelines
from app.medical_brain.prompts import build_medical_brain_instructions
from app.medical_brain.training.types import GeneratedClinicalCase, TrainingCaseResult
from app.services.consultation_red_flags import detect_consultation_red_flags


def _build_instructions(case: GeneratedClinicalCase) -> tuple[str, bool, list[str]]:
    session = [{"role": t.role, "content": t.content} for t in case.turns]
    user_message = case.turns[-1].content if case.turns else ""
    flags: list[str] = []
    for t in case.turns:
        if t.role == "user":
            flags.extend(detect_consultation_red_flags(t.content))
    flags = list(dict.fromkeys(flags))

    brain_input = build_medical_brain_input(
        patient_id=hash(case.id) % 100000,
        user_message=user_message,
        session_messages=session,
        known_facts={"profile": case.patient_profile, "opening_complaint": case.opening_message},
        topics_covered=["opening_complaint"],
        prior_complaints=[],
    )
    memory_input = ClinicalBrainInput(
        patient_id=brain_input.patient_id,
        user_message=user_message,
        complaint_category=brain_input.complaint_category,
        session_messages=session,
        known_facts=brain_input.known_facts,
        topics_covered=["opening_complaint"],
    )
    memory = retrieve_clinical_memory(memory_input)
    instructions = build_medical_brain_instructions(brain_input, memory, flags)
    return instructions, brain_input.is_emergency, flags


def validate_case_evidence(
    case: GeneratedClinicalCase,
    result: TrainingCaseResult | None = None,
) -> EvidenceReport:
    """Run guideline validation on a completed case — internal only."""
    instructions, is_emergency, flags = _build_instructions(case)
    routing_primary = result.routing_primary if result else ""
    routing_secondary = result.routing_secondary if result else []
    detected = flags + (result.missed_red_flags if result else [])

    if not routing_primary:
        bi = build_medical_brain_input(
            patient_id=hash(case.id) % 100000,
            user_message=case.opening_message,
            session_messages=[{"role": t.role, "content": t.content} for t in case.turns],
            known_facts={"profile": case.patient_profile},
            topics_covered=["opening_complaint"],
            prior_complaints=[],
        )
        routing_primary = bi.primary_specialty
        routing_secondary = bi.secondary_specialties
        is_emergency = bi.is_emergency

    report = validate_against_guidelines(
        case_id=case.id,
        gold_diagnosis=case.gold_diagnosis,
        specialty=case.specialty,
        guideline_references=case.guideline_references,
        patient_text=case.full_patient_text,
        instructions=instructions,
        detected_red_flags=detected,
        routing_primary=routing_primary,
        routing_secondary=routing_secondary,
        requires_emergency=case.requires_emergency,
        is_emergency=is_emergency,
        expected_urgency=case.urgency_level,
    )

    rules = resolve_applicable_rules(
        specialty=case.specialty,
        gold_diagnosis=case.gold_diagnosis,
        guideline_references=case.guideline_references,
        patient_text=case.full_patient_text,
    )
    if not report.passed:
        log_disagreements(report, rules, specialty=case.specialty)
    save_evidence_report(report)
    return report


def validate_batch_evidence(
    cases: list[GeneratedClinicalCase],
    results: list[TrainingCaseResult] | None = None,
) -> list[EvidenceReport]:
    result_map = {r.case_id: r for r in results} if results else {}
    return [validate_case_evidence(c, result_map.get(c.id)) for c in cases]

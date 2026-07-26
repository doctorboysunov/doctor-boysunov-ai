"""Medical Brain response parsing."""

from __future__ import annotations

from typing import Any

from app.clinical_brain.parse import limit_sentences
from app.clinical_brain.clinical_pathways import (
    PHASE_4_VERSION,
    apply_pathway_closure_gate,
    build_pathway_context,
)
from app.clinical_brain.senior_neurologist import (
    format_brief_summary_for_help_menu,
    format_patient_closure_summary,
    identify_dominant_complaint,
    merge_closure_from_response,
)
from app.clinical_brain.types import DoctorEmrUpdate
from app.medical_brain.physician_reasoning import apply_physician_reasoning, prior_internal_snapshot, sanitize_patient_reply
from app.medical_brain.reasoning import enrich_internal_reasoning
from app.medical_brain.types import MedicalBrainInternal, MedicalBrainOutput


def parse_medical_brain_response(
    data: dict[str, Any],
    *,
    detected_red_flags: list[str],
    primary_specialty: str,
    secondary_specialties: list[str],
    reasoning_context: dict[str, Any] | None = None,
    is_emergency: bool = False,
    instructions: str = "",
    turn_id: str = "",
    patient_text: str = "",
) -> MedicalBrainOutput:
    internal = MedicalBrainInternal.from_dict(data.get("medical_brain") or data.get("clinical_brain"))
    if not internal.primary_specialty:
        internal.primary_specialty = primary_specialty
    if not internal.secondary_specialties:
        internal.secondary_specialties = list(secondary_specialties)

    merged_flags = list(dict.fromkeys([*detected_red_flags, *internal.step4_red_flags]))
    internal.step4_red_flags = merged_flags

    if reasoning_context:
        internal = enrich_internal_reasoning(
            internal,
            reasoning_context,
            primary_specialty=primary_specialty,
            secondary_specialties=secondary_specialties,
            detected_flags=merged_flags,
            is_emergency=is_emergency,
        )
        internal = apply_physician_reasoning(
            internal,
            reasoning_context=reasoning_context,
            patient_text=patient_text,
            primary_specialty=primary_specialty,
            secondary_specialties=secondary_specialties,
            detected_flags=merged_flags,
            is_emergency=is_emergency,
            instructions=instructions,
            turn_id=turn_id,
        )

    topics = [str(item) for item in (data.get("topics_covered") or []) if str(item).strip()]
    if internal.step6_next_question_topic and internal.step6_next_question_topic not in topics:
        topics.append(internal.step6_next_question_topic)

    ready_menu = bool(data.get("ready_for_help_menu")) or internal.step7_ready_for_summary
    if internal.step7_stop_asking and internal.step6_clinical_confidence in {"high", "medium"}:
        ready_menu = ready_menu or internal.step7_ready_for_summary

    doctor = DoctorEmrUpdate.from_dict(data.get("doctor_emr"))
    if merged_flags and not doctor.red_flags_noted:
        doctor.red_flags_noted = merged_flags
    if internal.ranked_differential and not doctor.differential_diagnoses:
        doctor.differential_diagnoses = [
            f"{h.name} ({h.probability_pct}%)" for h in internal.ranked_differential[:6]
        ]

    dominant = identify_dominant_complaint(patient_text, "other_neurological")
    closure = merge_closure_from_response(data, internal, doctor, dominant=dominant)
    brief = str(data.get("brief_summary_for_patient") or "").strip()
    if ready_menu and not brief:
        brief = format_brief_summary_for_help_menu(closure)

    patient_reply = sanitize_patient_reply(
        limit_sentences(str(data.get("patient_reply") or "")),
        internal,
    )
    if internal.step7_ready_for_summary and not patient_reply:
        patient_reply = sanitize_patient_reply(format_patient_closure_summary(closure), internal)

    known_facts = dict(data.get("known_facts") or {})
    if reasoning_context:
        session_facts = dict(reasoning_context.get("known_facts") or {})
        session_facts.update(known_facts)
        known_facts = session_facts

    pathway_ctx = build_pathway_context(
        message=patient_text,
        known_facts=known_facts,
        topics_covered=topics,
        category_hint=dominant.dominant_category,
        detected_red_flags=merged_flags,
    )
    ready_summary, stop_asking = apply_pathway_closure_gate(
        pathway_ctx,
        ready_for_summary=internal.step7_ready_for_summary,
        stop_asking=internal.step7_stop_asking,
    )
    internal.step7_ready_for_summary = ready_summary
    internal.step7_stop_asking = stop_asking
    if not pathway_ctx.ready_for_closure:
        ready_menu = False

    if not closure.neurological_syndrome:
        closure.neurological_syndrome = pathway_ctx.syndrome_label_uz

    known_facts["prior_internal"] = prior_internal_snapshot(internal)
    known_facts["consultation_closure"] = closure.to_dict()
    known_facts["dominant_complaint"] = dominant.dominant_label
    known_facts["dominant_complaint_rationale"] = dominant.rationale
    known_facts["clinical_pathway_id"] = pathway_ctx.pathway_id
    known_facts["neurological_syndrome"] = pathway_ctx.syndrome
    known_facts["pathway_completion_pct"] = pathway_ctx.completion_pct
    known_facts["pathway_ready_for_closure"] = pathway_ctx.ready_for_closure
    known_facts["clinical_pathway"] = pathway_ctx.to_dict()
    known_facts["phase_4_version"] = PHASE_4_VERSION

    return MedicalBrainOutput(
        patient_reply=patient_reply,
        ready_for_help_menu=ready_menu,
        brief_summary_for_patient=limit_sentences(brief, 3),
        known_facts=known_facts,
        topics_covered=topics,
        doctor_emr=doctor,
        internal=internal,
        primary_specialty=primary_specialty,  # type: ignore[arg-type]
        secondary_specialties=secondary_specialties,  # type: ignore[arg-type]
    )

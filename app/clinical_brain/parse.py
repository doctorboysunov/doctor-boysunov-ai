"""Clinical Brain response parsing utilities."""

from __future__ import annotations

import json
import re
from typing import Any

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
from app.clinical_brain.types import ClinicalBrainInternal, ClinicalBrainOutput, DoctorEmrUpdate


def extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def limit_sentences(text: str, max_sentences: int = 4) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    parts = [part.strip() for part in parts if part.strip()]
    if len(parts) <= max_sentences:
        return cleaned
    return " ".join(parts[:max_sentences]).strip()


def conversation_input(history: list[dict[str, str]], user_message: str) -> str | list[dict[str, Any]]:
    if not history or (len(history) == 1 and history[0].get("role") == "user"):
        return user_message
    return [
        {"role": m["role"], "content": m["content"], "type": "message"}
        for m in history
        if m.get("role") in {"user", "assistant"} and m.get("content")
    ]


def parse_clinical_brain_response(
    data: dict[str, Any],
    *,
    detected_red_flags: list[str],
    user_message: str = "",
) -> ClinicalBrainOutput:
    internal = ClinicalBrainInternal.from_dict(data.get("clinical_brain") or data.get("internal_reasoning"))
    merged_flags = list(dict.fromkeys([*detected_red_flags, *internal.step4_red_flags]))
    internal.step4_red_flags = merged_flags

    topics = [str(item) for item in (data.get("topics_covered") or []) if str(item).strip()]
    if internal.step6_next_question_topic and internal.step6_next_question_topic not in topics:
        topics.append(internal.step6_next_question_topic)

    ready_menu = bool(data.get("ready_for_help_menu")) or internal.step7_ready_for_summary
    if internal.step7_stop_asking and internal.step6_clinical_confidence in {"high", "medium"}:
        ready_menu = ready_menu or internal.step7_ready_for_summary

    doctor = DoctorEmrUpdate.from_dict(data.get("doctor_emr"))
    if merged_flags and not doctor.red_flags_noted:
        doctor.red_flags_noted = merged_flags

    dominant = identify_dominant_complaint(
        user_message or internal.step1_patient_meaning or "",
        "other_neurological",
    )
    closure = merge_closure_from_response(data, internal, doctor, dominant=dominant)
    brief = str(data.get("brief_summary_for_patient") or "").strip()
    if ready_menu and not brief:
        brief = format_brief_summary_for_help_menu(closure)

    patient_reply = limit_sentences(str(data.get("patient_reply") or ""))
    if internal.step7_ready_for_summary and not patient_reply:
        patient_reply = format_patient_closure_summary(closure)

    known_facts = dict(data.get("known_facts") or {})
    pathway_ctx = build_pathway_context(
        message=user_message or internal.step1_patient_meaning or "",
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

    known_facts["consultation_closure"] = closure.to_dict()
    known_facts["dominant_complaint"] = dominant.dominant_label
    known_facts["dominant_complaint_rationale"] = dominant.rationale
    known_facts["clinical_pathway_id"] = pathway_ctx.pathway_id
    known_facts["neurological_syndrome"] = pathway_ctx.syndrome
    known_facts["pathway_completion_pct"] = pathway_ctx.completion_pct
    known_facts["pathway_ready_for_closure"] = pathway_ctx.ready_for_closure
    known_facts["clinical_pathway"] = pathway_ctx.to_dict()
    known_facts["phase_4_version"] = PHASE_4_VERSION

    return ClinicalBrainOutput(
        patient_reply=patient_reply,
        ready_for_help_menu=ready_menu,
        brief_summary_for_patient=limit_sentences(brief, 3),
        known_facts=known_facts,
        topics_covered=topics,
        doctor_emr=doctor,
        internal=internal,
    )

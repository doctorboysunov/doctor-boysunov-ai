"""Universal Medical Brain engine — coordinates all specialties."""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from app.clinical_brain.memory import retrieve_clinical_memory
from app.clinical_brain.parse import conversation_input, extract_json, limit_sentences
from app.clinical_brain.senior_neurologist import PHASE_3_VERSION
from app.clinical_brain.clinical_pathways import PHASE_4_VERSION
from app.clinical_brain.types import ClinicalBrainInput
from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.medical_brain.parse import parse_medical_brain_response
from app.medical_brain.reasoning import build_reasoning_context
from app.medical_brain.prompts import build_medical_brain_instructions
from app.medical_brain.router import route_medical_specialties
from app.medical_brain.types import MedicalBrainInput, MedicalBrainOutput
from app.safety.safety_layer import enforce_safety
from app.medical_brain.physician_reasoning import sanitize_patient_reply
from app.clinical_brain.clinical_pathways.recognition import resolve_complaint_category
from app.services.consultation_classifier import classify_complaint
from app.services.consultation_red_flags import detect_consultation_red_flags

logger = logging.getLogger("doctor_boysunov.medical_brain")

client = OpenAI(api_key=OPENAI_API_KEY)


def run_medical_brain(input_data: MedicalBrainInput) -> MedicalBrainOutput:
    """Execute Universal Medical Brain pipeline for one patient message."""
    memory_input = ClinicalBrainInput(
        patient_id=input_data.patient_id,
        user_message=input_data.user_message,
        complaint_category=input_data.complaint_category,
        session_messages=input_data.session_messages,
        known_facts=input_data.known_facts,
        topics_covered=input_data.topics_covered,
        prior_complaints=input_data.prior_complaints,
        visit_history=input_data.visit_history,
    )
    memory = retrieve_clinical_memory(memory_input)
    user_turns = [m["content"] for m in input_data.session_messages if m.get("role") == "user"]
    routing_text = " ".join(user_turns) if len(user_turns) > 1 else input_data.user_message
    detected_red_flags = list(dict.fromkeys(
        f for part in ([routing_text] if routing_text else [input_data.user_message])
        for f in detect_consultation_red_flags(part)
    ))

    instructions = build_medical_brain_instructions(
        input_data=input_data,
        memory=memory,
        detected_red_flags=detected_red_flags,
    )

    reasoning_context = build_reasoning_context(
        known_facts=input_data.known_facts,
        session_messages=input_data.session_messages,
        topics_covered=input_data.topics_covered,
        detected_flags=detected_red_flags,
        is_emergency=input_data.is_emergency,
        primary_specialty=input_data.primary_specialty,
        secondary_specialties=input_data.secondary_specialties,
    )
    reasoning_context["prior_internal"] = input_data.known_facts.get("prior_internal") or {}

    history = list(input_data.session_messages)
    if not history or history[-1].get("content") != input_data.user_message:
        history.append({"role": "user", "content": input_data.user_message})

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=conversation_input(history, input_data.user_message),
        instructions=instructions,
    )
    raw = response.output_text or ""
    logger.info(
        "medical_brain_turn patient_id=%s primary=%s secondary=%s raw_len=%s",
        input_data.patient_id,
        input_data.primary_specialty,
        input_data.secondary_specialties,
        len(raw),
    )

    patient_text = " ".join(
        m["content"] for m in input_data.session_messages if m.get("role") == "user"
    ) or input_data.user_message

    parsed = parse_medical_brain_response(
        extract_json(raw),
        detected_red_flags=detected_red_flags,
        primary_specialty=input_data.primary_specialty,
        secondary_specialties=input_data.secondary_specialties,
        reasoning_context=reasoning_context,
        is_emergency=input_data.is_emergency,
        instructions=instructions,
        turn_id=f"patient_{input_data.patient_id}_turn_{len(user_turns)}",
        patient_text=patient_text,
    )

    if not parsed.internal.step2_memory_summary:
        parsed.internal.step2_memory_summary = str(memory.get("memory_summary") or "")[:500]

    safe_reply, _meta = enforce_safety(
        user_message=input_data.user_message,
        ai_response=parsed.patient_reply,
    )
    parsed.patient_reply = sanitize_patient_reply(limit_sentences(safe_reply), parsed.internal)
    return parsed


def build_medical_brain_input(
    *,
    patient_id: int,
    user_message: str,
    session_messages: list[dict[str, str]],
    known_facts: dict[str, Any],
    topics_covered: list[str],
    prior_complaints: list[str],
    visit_history: dict[str, Any] | None = None,
    primary_specialty: str | None = None,
    secondary_specialties: list[str] | None = None,
) -> MedicalBrainInput:
    """Build input with automatic specialty routing if not provided."""
    detected_flags = detect_consultation_red_flags(user_message)
    # Multi-turn: route on full patient narrative, not just the latest message
    routing_text = user_message
    if session_messages:
        user_parts = [m["content"] for m in session_messages if m.get("role") == "user"]
        if len(user_parts) > 1:
            routing_text = " ".join(user_parts)
            detected_flags = list(dict.fromkeys(
                f for part in user_parts for f in detect_consultation_red_flags(part)
            ))
    routing = route_medical_specialties(routing_text)

    # Clinical reasoning: red-flag signals reinforce emergency classification
    is_emergency = routing.is_emergency or bool(detected_flags)

    primary = primary_specialty or routing.primary
    secondary = secondary_specialties if secondary_specialties is not None else routing.secondary

    # Ensure emergency routing when red flags imply urgency but router missed secondary
    if is_emergency and "emergency_medicine" not in secondary and primary != "emergency_medicine":
        secondary = ["emergency_medicine", *secondary][:4]

    category = resolve_complaint_category(
        routing_text,
        category_hint=classify_complaint(routing_text),
        known_facts=known_facts,
    )

    return MedicalBrainInput(
        patient_id=patient_id,
        user_message=user_message,
        primary_specialty=primary,  # type: ignore[arg-type]
        secondary_specialties=secondary,  # type: ignore[arg-type]
        complaint_category=category,
        session_messages=session_messages,
        known_facts=known_facts,
        topics_covered=topics_covered,
        prior_complaints=prior_complaints,
        visit_history=visit_history,
        specialty_confidence=routing.confidence,
        is_emergency=is_emergency,
    )


def medical_brain_to_legacy_summary(output: MedicalBrainOutput) -> dict[str, Any]:
    """Map Medical Brain output for session persistence and CRM integration."""
    return {
        "medical_brain": output.internal.to_dict(),
        "clinical_brain": output.internal.to_dict(),
        "doctor_emr": output.doctor_emr.to_dict(),
        "primary_specialty": output.primary_specialty,
        "secondary_specialties": output.secondary_specialties,
        "consultation_closure": output.known_facts.get("consultation_closure") or {},
        "dominant_complaint": output.known_facts.get("dominant_complaint"),
        "dominant_complaint_rationale": output.known_facts.get("dominant_complaint_rationale"),
        "phase_3_version": PHASE_3_VERSION,
        "phase_4_version": PHASE_4_VERSION,
        "clinical_pathway_id": output.known_facts.get("clinical_pathway_id"),
        "neurological_syndrome": output.known_facts.get("neurological_syndrome"),
        "pathway_completion_pct": output.known_facts.get("pathway_completion_pct"),
        "internal_reasoning": {
            "what_i_know": output.internal.what_i_know,
            "story_synthesis": output.internal.story_synthesis,
            "missing_information": output.internal.step5_missing_information,
            "emergency_assessment": output.internal.step4_emergency_assessment,
            "emergency_probability": output.internal.emergency_probability,
            "recommended_urgency": output.internal.recommended_urgency,
            "hypotheses": [h.name for h in output.internal.step3_hypotheses],
            "must_not_miss": [h.name for h in output.internal.step3_must_not_miss],
            "alternatives": [h.name for h in output.internal.step3_alternatives],
            "possible_neurological_causes": output.internal.possible_causes,
            "ranked_differential": [
                {"name": h.name, "probability_pct": h.probability_pct, "probability": h.probability}
                for h in output.internal.ranked_differential
            ],
            "clinical_confidence_score": output.internal.clinical_confidence_score,
            "evidence_validation": output.internal.evidence_validation,
            "next_question_topic": output.internal.step6_next_question_topic,
            "next_question_rationale": output.internal.step6_next_question_rationale,
            "primary_specialty": output.primary_specialty,
            "secondary_specialties": output.secondary_specialties,
        },
    }

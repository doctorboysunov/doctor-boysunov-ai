"""Clinical Brain engine — 7-step pipeline orchestrator."""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from app.clinical_brain.knowledge import format_knowledge_reference
from app.clinical_brain.memory import retrieve_clinical_memory
from app.clinical_brain.parse import conversation_input, extract_json, limit_sentences, parse_clinical_brain_response
from app.clinical_brain.prompts import build_clinical_brain_instructions
from app.clinical_brain.types import ClinicalBrainInput, ClinicalBrainOutput
from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.safety.safety_layer import enforce_safety
from app.services.consultation_red_flags import detect_consultation_red_flags

logger = logging.getLogger("doctor_boysunov.clinical_brain")

client = OpenAI(api_key=OPENAI_API_KEY)


def run_clinical_brain(input_data: ClinicalBrainInput) -> ClinicalBrainOutput:
    """Execute the full Clinical Brain pipeline for one patient message."""
    memory = retrieve_clinical_memory(input_data)
    knowledge_reference = format_knowledge_reference(input_data.complaint_category)
    detected_red_flags = detect_consultation_red_flags(input_data.user_message)

    instructions = build_clinical_brain_instructions(
        input_data=input_data,
        memory=memory,
        knowledge_reference=knowledge_reference,
        detected_red_flags=detected_red_flags,
    )

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
        "clinical_brain_turn patient_id=%s category=%s raw_len=%s flags=%s",
        input_data.patient_id,
        input_data.complaint_category,
        len(raw),
        detected_red_flags,
    )

    parsed = parse_clinical_brain_response(
        extract_json(raw),
        detected_red_flags=detected_red_flags,
        user_message=input_data.user_message,
    )

    if not parsed.internal.step2_memory_summary:
        parsed.internal.step2_memory_summary = str(memory.get("memory_summary") or "")[:500]

    safe_reply, _meta = enforce_safety(
        user_message=input_data.user_message,
        ai_response=parsed.patient_reply,
    )
    parsed.patient_reply = limit_sentences(safe_reply)
    return parsed


def clinical_brain_to_legacy_summary(output: ClinicalBrainOutput) -> dict[str, Any]:
    """Map Clinical Brain output for session persistence and CRM integration."""
    return {
        "clinical_brain": output.internal.to_dict(),
        "doctor_emr": output.doctor_emr.to_dict(),
        "internal_reasoning": {
            "what_i_know": output.internal.what_i_know,
            "missing_information": output.internal.step5_missing_information,
            "emergency_assessment": output.internal.step4_emergency_assessment,
            "possible_neurological_causes": output.internal.possible_neurological_causes,
            "next_question_topic": output.internal.step6_next_question_topic,
            "next_question_rationale": output.internal.step6_next_question_rationale,
        },
    }

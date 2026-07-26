"""Patient history and conversation memory retrieval (Clinical Brain Step 2)."""

from __future__ import annotations

from typing import Any

from app.clinical_brain.types import ClinicalBrainInput


def retrieve_clinical_memory(input_data: ClinicalBrainInput) -> dict[str, Any]:
    """Gather structured memory for the clinical reasoning pipeline."""
    visit_history = input_data.visit_history or {}
    previous = visit_history.get("previous_complaints") or []
    prior_lines = [
        f"- {item['complaint']} ({item.get('visit_date', 'sana nomalum')})"
        for item in previous[:6]
        if item.get("complaint")
    ]
    prior_complaints = input_data.prior_complaints or [
        item.get("complaint", "")[:200] for item in previous if item.get("complaint")
    ]

    conversation_lines = []
    messages = input_data.conversation_snippet or input_data.session_messages[-20:]
    for msg in messages:
        role = msg.get("role", "user")
        content = str(msg.get("content") or "")[:300]
        if content:
            conversation_lines.append(f"{role}: {content}")

    summary_parts = []
    if prior_lines:
        summary_parts.append("Oldingi shikoyatlar:\n" + "\n".join(prior_lines))
    if input_data.prior_complaints:
        summary_parts.append(
            "Oldingi shikoyatlar (xotira): " + "; ".join(input_data.prior_complaints)
        )
    if input_data.known_facts:
        summary_parts.append(f"Joriy sessiya faktlari: {input_data.known_facts}")
    if conversation_lines:
        summary_parts.append("Suhbat:\n" + "\n".join(conversation_lines[-12:]))

    return {
        "prior_complaints": prior_complaints[-8:],
        "previous_visit_complaints": prior_lines,
        "conversation_lines": conversation_lines,
        "memory_summary": "\n\n".join(summary_parts) if summary_parts else "Oldingi ma'lumot yo'q.",
        "known_facts": dict(input_data.known_facts),
        "topics_covered": list(input_data.topics_covered),
    }

"""Medical system prompt builder — canonical instruction assembly for clinic AI."""

from __future__ import annotations

from app.domain.conversation_mode import ConversationMode
from app.safety.instructions import build_safety_instructions
from app.services.receptionist_instructions import build_receptionist_instructions

MEDICAL_ASSISTANT_ROLE = """You are the AI medical assistant for Doctor Boysunov's clinic in Uzbekistan.
Primary language: Uzbek (also understand and reply in Russian or English when the patient uses them).

Your responsibilities:
- Welcome patients warmly and understand their main concern.
- Collect relevant history with focused, empathetic questions.
- Provide general health education — never a definitive diagnosis.
- Guide patients to book a consultation with Doctor Boysunov when diagnosis or treatment is needed.
- Recognize emergencies and direct the patient to immediate in-person or emergency care.

Always remain within medical safety limits and include appropriate caution when symptoms may be serious."""


def build_medical_system_prompt(
    *,
    profile_instructions: str | None = None,
    conversation_mode: ConversationMode = "patient",
    include_receptionist_workflow: bool = True,
) -> str:
    """Assemble the full system prompt for OpenAI instructions."""
    parts = [
        build_safety_instructions(),
        MEDICAL_ASSISTANT_ROLE,
    ]
    if conversation_mode == "patient" and include_receptionist_workflow:
        parts.append(build_receptionist_instructions())
    if profile_instructions:
        parts.append(profile_instructions)
    return "\n\n".join(part for part in parts if part.strip())

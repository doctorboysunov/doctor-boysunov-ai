"""Build long-term memory instructions for AI context."""

from __future__ import annotations

from app.domain.entities.patient_memory import PatientMemory
from app.domain.patient_profile_fields import PROFILE_CONTEXT_FIELDS
from app.services.patient_context import build_profile_instructions


def build_memory_instructions(
    *,
    profile: dict | None,
    memories: list[PatientMemory],
    prior_conversation_summaries: list[str] | None = None,
) -> str | None:
    """Merge profile, semantic memories, and prior conversation summaries."""
    sections: list[str] = []

    profile_block = build_profile_instructions(profile)
    if profile_block:
        sections.append(profile_block)

    extra_lines: list[str] = []
    for memory in memories:
        if not memory.value:
            continue
        if (
            memory.key in PROFILE_CONTEXT_FIELDS
            and profile
            and profile.get(memory.key)
        ):
            continue
        extra_lines.append(f"- {memory.key}: {memory.value}")

    if extra_lines:
        sections.append(
            "Long-term patient memory (facts remembered across conversations):\n"
            + "\n".join(extra_lines)
        )

    summaries = [
        summary.strip()
        for summary in (prior_conversation_summaries or [])
        if summary and summary.strip()
    ]
    if summaries:
        formatted = "\n".join(f"- {summary}" for summary in summaries)
        sections.append(
            "Previous conversation summaries (use for continuity; do not ask the patient to repeat):\n"
            + formatted
        )

    if not sections:
        return None
    return "\n\n".join(sections)

"""Load conversation context for AI requests."""

from __future__ import annotations

from dataclasses import dataclass

from app.container import get_container
from app.domain.channels import ChannelType, DEFAULT_CHANNEL
from app.repositories.conversation_repository import get_last_messages
from app.repositories.patient_profile_repository import get_or_create_patient_profile


@dataclass(frozen=True)
class ConversationContext:
    conversation_id: int
    user_id: int
    channel: ChannelType
    history: list[dict[str, str]]
    patient_profile: dict
    context_instructions: str | None


def load_conversation_context(
    user_id: int,
    *,
    conversation_id: int | None = None,
    channel: ChannelType = DEFAULT_CHANNEL,
    history_limit: int = 10,
) -> ConversationContext:
    """Load short-term history plus long-term memory for an AI turn."""
    from app.application.memory.context_builder import build_memory_instructions

    container = get_container()
    active_conversation_id = conversation_id or container.conversations.get_or_create_active_conversation(
        user_id,
        channel=channel,
    )
    history = get_last_messages(active_conversation_id, limit=history_limit)
    patient_profile = get_or_create_patient_profile(user_id)
    memories = container.memories.get_memories(user_id)
    prior_summaries = container.conversations.get_prior_conversation_summaries(
        user_id,
        exclude_conversation_id=active_conversation_id,
    )
    context_instructions = build_memory_instructions(
        profile=patient_profile,
        memories=memories,
        prior_conversation_summaries=prior_summaries,
    )
    return ConversationContext(
        conversation_id=active_conversation_id,
        user_id=user_id,
        channel=channel,
        history=history,
        patient_profile=patient_profile,
        context_instructions=context_instructions,
    )

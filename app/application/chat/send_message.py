"""Send message use case — orchestrates conversation persistence and AI reply."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.chat.load_conversation_context import load_conversation_context
from app.container import get_container
from app.domain.channels import ChannelType, DEFAULT_CHANNEL
from app.domain.conversation_mode import ConversationMode
from app.services.openai_service import ask_ai


@dataclass(frozen=True)
class SendMessageResult:
    reply: str
    conversation_id: int


def send_patient_message(
    *,
    user_id: int,
    user_message: str,
    patient_profile: dict | None = None,
    conversation_mode: ConversationMode = "patient",
    channel: ChannelType = DEFAULT_CHANNEL,
    conversation_id: int | None = None,
    history_limit: int = 10,
) -> SendMessageResult:
    """Persist user message, call AI with full memory context, persist assistant reply."""
    container = get_container()
    active_conversation_id = conversation_id or container.conversations.get_or_create_active_conversation(
        user_id,
        channel=channel,
    )
    container.conversations.save_message(active_conversation_id, "user", user_message)

    context = load_conversation_context(
        user_id,
        conversation_id=active_conversation_id,
        channel=channel,
        history_limit=history_limit,
    )
    profile = patient_profile or context.patient_profile
    reply = ask_ai(
        context.history,
        patient_profile=profile,
        conversation_mode=conversation_mode,
        context_instructions=context.context_instructions,
    )
    container.conversations.save_message(active_conversation_id, "assistant", reply)
    return SendMessageResult(reply=reply, conversation_id=active_conversation_id)

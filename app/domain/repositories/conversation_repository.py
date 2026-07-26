"""Conversation and message repository interface."""

from __future__ import annotations

from typing import Protocol

from app.domain.channels import ChannelType
from app.domain.entities.message import Message


class ConversationRepository(Protocol):
    def get_or_create_active_conversation(
        self,
        user_id: int,
        *,
        channel: ChannelType = "telegram",
        external_thread_id: str | None = None,
    ) -> int: ...

    def save_message(self, conversation_id: int, role: str, content: str) -> None: ...

    def get_last_messages(self, conversation_id: int, limit: int = 10) -> list[Message]: ...

    def set_last_response_id(self, conversation_id: int, response_id: str) -> None: ...

    def get_last_response_id(self, conversation_id: int) -> str | None: ...

    def close_conversation(self, conversation_id: int, *, summary: str | None = None) -> None: ...

    def set_conversation_summary(self, conversation_id: int, summary: str) -> None: ...

    def get_prior_conversation_summaries(
        self,
        user_id: int,
        *,
        exclude_conversation_id: int | None = None,
        limit: int = 5,
    ) -> list[str]: ...

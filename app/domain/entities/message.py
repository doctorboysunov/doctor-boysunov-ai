"""Message entity — single turn in a conversation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MessageRole = Literal["user", "assistant", "system"]


@dataclass(frozen=True)
class Message:
    id: int
    conversation_id: int
    role: MessageRole
    content: str
    created_at: str = ""

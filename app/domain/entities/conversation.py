"""Conversation entity — chat thread for one patient."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Conversation:
    id: int
    user_id: int
    status: str = "active"
    channel: str = "telegram"
    external_thread_id: str | None = None
    summary: str | None = None
    last_response_id: str | None = None
    closed_at: str | None = None
    created_at: str = ""
    updated_at: str = ""

"""User entity — Telegram patient identity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    telegram_id: int | None
    username: str | None = None
    full_name: str | None = None
    registration_source: str = "telegram"
    created_at: str = ""

"""User repository interface."""

from __future__ import annotations

from typing import Protocol

from app.domain.entities.user import User


class UserRepository(Protocol):
    def upsert_telegram_user(
        self,
        telegram_id: int,
        *,
        username: str | None = None,
        full_name: str | None = None,
    ) -> int: ...

    def get_by_telegram_id(self, telegram_id: int) -> User | None: ...

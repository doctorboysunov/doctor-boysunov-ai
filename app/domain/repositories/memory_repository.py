"""Patient memory repository interface."""

from __future__ import annotations

from typing import Protocol

from app.domain.entities.patient_memory import PatientMemory


class MemoryRepository(Protocol):
    def upsert_memory(
        self,
        user_id: int,
        key: str,
        value: str,
        *,
        source_message_id: int | None = None,
        confidence: float | None = None,
    ) -> None: ...

    def get_memories(self, user_id: int) -> list[PatientMemory]: ...

    def delete_memory(self, user_id: int, key: str) -> None: ...

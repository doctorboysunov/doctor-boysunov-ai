"""Patient memory entity — structured long-term fact about a patient."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatientMemory:
    user_id: int
    key: str
    value: str
    id: int | None = None
    source_message_id: int | None = None
    confidence: float | None = None
    updated_at: str = ""

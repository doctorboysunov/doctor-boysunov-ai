"""Persistent long-term patient memory storage."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection
from app.domain.patient_profile_fields import PROFILE_FIELDS
from app.repositories import patient_profile_repository as profile_repo

logger = logging.getLogger("doctor_boysunov.memory")

_NUMERIC_PROFILE_FIELDS = frozenset({"age", "height_cm", "weight_kg"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _memory_text(value: Any) -> str:
    return str(value).strip()


def _coerce_profile_value(key: str, value: Any) -> Any:
    if key in _NUMERIC_PROFILE_FIELDS:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return value


def _row_to_memory(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "key": row["memory_key"],
        "value": row["memory_value"],
        "source_message_id": row["source_message_id"],
        "confidence": row["confidence"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def upsert_memory(
    user_id: int,
    key: str,
    value: Any,
    *,
    source_message_id: int | None = None,
    confidence: float | None = None,
) -> None:
    if not key.strip():
        raise ValueError("memory key must not be empty")
    memory_value = _memory_text(value)
    if not memory_value:
        raise ValueError("memory value must not be empty")

    now = _utc_now()
    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id FROM patient_memories
            WHERE user_id = ? AND memory_key = ?
            """,
            (user_id, key),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO patient_memories (
                    user_id, memory_key, memory_value,
                    source_message_id, confidence, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, key, memory_value, source_message_id, confidence, now, now),
            )
        else:
            conn.execute(
                """
                UPDATE patient_memories
                SET memory_value = ?,
                    source_message_id = COALESCE(?, source_message_id),
                    confidence = COALESCE(?, confidence),
                    updated_at = ?
                WHERE user_id = ? AND memory_key = ?
                """,
                (memory_value, source_message_id, confidence, now, user_id, key),
            )
        conn.commit()

    if key in PROFILE_FIELDS:
        profile_repo.update_patient_profile(
            user_id,
            **{key: _coerce_profile_value(key, value)},
        )

    logger.info(
        "upsert_memory user_id=%s key=%s value=%r source_message_id=%s",
        user_id,
        key,
        memory_value,
        source_message_id,
    )


def get_memories(user_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, memory_key, memory_value,
                   source_message_id, confidence, created_at, updated_at
            FROM patient_memories
            WHERE user_id = ?
            ORDER BY memory_key ASC, id ASC
            """,
            (user_id,),
        ).fetchall()
    return [_row_to_memory(row) for row in rows]


def get_memory(user_id: int, key: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, memory_key, memory_value,
                   source_message_id, confidence, created_at, updated_at
            FROM patient_memories
            WHERE user_id = ? AND memory_key = ?
            """,
            (user_id, key),
        ).fetchone()
    return None if row is None else _row_to_memory(row)


def delete_memory(user_id: int, key: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM patient_memories WHERE user_id = ? AND memory_key = ?",
            (user_id, key),
        )
        conn.commit()

    if key in PROFILE_FIELDS:
        profile_repo.update_patient_profile(user_id, **{key: None})

    logger.info("delete_memory user_id=%s key=%s", user_id, key)

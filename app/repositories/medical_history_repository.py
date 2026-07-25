import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection
from app.domain.medical_history_types import MEDICAL_RECORD_TYPES

logger = logging.getLogger("doctor_boysunov.medical_history")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_record(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "record_type": row["record_type"],
        "content": row["content"],
        "notes": row["notes"],
        "event_date": row["event_date"],
        "created_at": row["created_at"],
    }


def _validate_record_type(record_type: str) -> None:
    if record_type not in MEDICAL_RECORD_TYPES:
        raise ValueError(
            f"Invalid record_type {record_type!r}. "
            f"Expected one of: {', '.join(MEDICAL_RECORD_TYPES)}"
        )


def add_medical_record(
    user_id: int,
    record_type: str,
    content: str,
    *,
    notes: str | None = None,
    event_date: str | None = None,
) -> dict[str, Any]:
    _validate_record_type(record_type)
    cleaned = content.strip()
    if not cleaned:
        raise ValueError("Medical history content must not be empty")

    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO medical_history (
                user_id, record_type, content, notes, event_date, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, record_type, cleaned, notes, event_date, now),
        )
        conn.commit()
        record_id = int(cursor.lastrowid)

    logger.info(
        "add_medical_record user_id=%s record_id=%s type=%s",
        user_id,
        record_id,
        record_type,
    )
    return get_medical_record(record_id)


def get_medical_record(record_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, record_type, content, notes, event_date, created_at
            FROM medical_history
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()

    if row is None:
        raise ValueError(f"Medical history record not found: id={record_id}")

    return _row_to_record(row)


def get_medical_history(
    user_id: int,
    *,
    record_type: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if record_type is not None:
        _validate_record_type(record_type)

    query = """
        SELECT id, user_id, record_type, content, notes, event_date, created_at
        FROM medical_history
        WHERE user_id = ?
    """
    params: list[Any] = [user_id]

    if record_type is not None:
        query += " AND record_type = ?"
        params.append(record_type)

    query += " ORDER BY id ASC"

    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    records = [_row_to_record(row) for row in rows]
    logger.debug(
        "get_medical_history user_id=%s type=%s count=%s",
        user_id,
        record_type,
        len(records),
    )
    return records


def count_medical_records(user_id: int, record_type: str | None = None) -> int:
    if record_type is not None:
        _validate_record_type(record_type)

    query = "SELECT COUNT(*) AS count FROM medical_history WHERE user_id = ?"
    params: list[Any] = [user_id]

    if record_type is not None:
        query += " AND record_type = ?"
        params.append(record_type)

    with get_connection() as conn:
        count = conn.execute(query, params).fetchone()["count"]

    return int(count)


def get_medical_history_counts(user_id: int) -> dict[str, int]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT record_type, COUNT(*) AS count
            FROM medical_history
            WHERE user_id = ?
            GROUP BY record_type
            """,
            (user_id,),
        ).fetchall()

    counts = {record_type: 0 for record_type in MEDICAL_RECORD_TYPES}
    for row in rows:
        counts[row["record_type"]] = int(row["count"])
    return counts

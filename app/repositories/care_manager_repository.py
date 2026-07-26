"""Care manager record persistence for EMR."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection
from app.domain.care_manager import CARE_EVENT_TYPES, CARE_OUTCOMES

logger = logging.getLogger("doctor_boysunov.care_manager")

_RECORD_COLUMNS = (
    "id",
    "patient_id",
    "follow_up_id",
    "sequence_number",
    "event_type",
    "outcome",
    "message_text",
    "reply_text",
    "event_date",
    "created_at",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_record(row) -> dict[str, Any]:
    record = {column: row[column] for column in _RECORD_COLUMNS}
    record["id"] = int(record["id"])
    record["patient_id"] = int(record["patient_id"])
    if record["follow_up_id"] is not None:
        record["follow_up_id"] = int(record["follow_up_id"])
    if record["sequence_number"] is not None:
        record["sequence_number"] = int(record["sequence_number"])
    return record


def _validate_event_type(event_type: str) -> None:
    if event_type not in CARE_EVENT_TYPES:
        raise ValueError(f"Invalid care event type: {event_type!r}")


def _validate_outcome(outcome: str | None) -> None:
    if outcome is not None and outcome not in CARE_OUTCOMES:
        raise ValueError(f"Invalid care outcome: {outcome!r}")


def add_care_manager_record(
    *,
    patient_id: int,
    follow_up_id: int | None,
    sequence_number: int | None,
    event_type: str,
    outcome: str | None = None,
    message_text: str | None = None,
    reply_text: str | None = None,
    event_date: str,
) -> dict[str, Any]:
    _validate_event_type(event_type)
    _validate_outcome(outcome)
    now = _utc_now()

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO care_manager_records (
                patient_id, follow_up_id, sequence_number, event_type,
                outcome, message_text, reply_text, event_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                follow_up_id,
                sequence_number,
                event_type,
                outcome,
                message_text,
                reply_text,
                event_date,
                now,
            ),
        )
        record_id = int(cursor.lastrowid)
        row = conn.execute(
            "SELECT * FROM care_manager_records WHERE id = ?",
            (record_id,),
        ).fetchone()
        conn.commit()

    record = _row_to_record(row)
    logger.info(
        "care_manager_record patient_id=%s follow_up_id=%s event_type=%s outcome=%s",
        patient_id,
        follow_up_id,
        event_type,
        outcome,
    )
    return record


def list_care_manager_records_for_patient(patient_id: int) -> list[dict[str, Any]]:
    columns = ", ".join(_RECORD_COLUMNS)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {columns}
            FROM care_manager_records
            WHERE patient_id = ?
            ORDER BY event_date DESC, id DESC
            """,
            (patient_id,),
        ).fetchall()
    return [_row_to_record(row) for row in rows]


def list_patients_by_latest_outcome(outcome: str) -> list[dict[str, Any]]:
    """Patients whose most recent care reply has the given outcome."""
    _validate_outcome(outcome)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT f.patient_id, f.id AS follow_up_id, f.sequence_number,
                   f.response_outcome, f.patient_reply_text, f.scheduled_date,
                   f.high_priority, f.updated_at
            FROM follow_ups f
            INNER JOIN (
                SELECT patient_id, MAX(id) AS max_id
                FROM follow_ups
                WHERE response_outcome = ?
                  AND status != 'cancelled'
                GROUP BY patient_id
            ) latest ON f.id = latest.max_id
            ORDER BY f.updated_at DESC
            """,
            (outcome,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_patients_no_response() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT patient_id, id AS follow_up_id, sequence_number,
                   response_outcome, scheduled_date, retry_count, updated_at
            FROM follow_ups
            WHERE status = 'no_response'
            ORDER BY updated_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]

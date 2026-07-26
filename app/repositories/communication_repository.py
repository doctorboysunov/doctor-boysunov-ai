"""Persistent communication channel and delivery history storage."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection
from app.domain.communication import COMMUNICATION_CHANNELS, DELIVERY_STATUSES

logger = logging.getLogger("doctor_boysunov.communication")

_CHANNEL_COLUMNS = (
    "id",
    "patient_id",
    "channel",
    "address",
    "enabled",
    "verified_at",
    "created_at",
    "updated_at",
)

_DELIVERY_COLUMNS = (
    "id",
    "patient_id",
    "channel",
    "source_type",
    "source_id",
    "message_text",
    "status",
    "provider_name",
    "provider_message_id",
    "error_message",
    "attempt_number",
    "parent_delivery_id",
    "replied_at",
    "reply_text",
    "created_at",
    "updated_at",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_channel(row) -> dict[str, Any]:
    record = {column: row[column] for column in _CHANNEL_COLUMNS}
    record["id"] = int(record["id"])
    record["patient_id"] = int(record["patient_id"])
    record["enabled"] = bool(record["enabled"])
    return record


def _row_to_delivery(row) -> dict[str, Any]:
    record = {column: row[column] for column in _DELIVERY_COLUMNS}
    record["id"] = int(record["id"])
    record["patient_id"] = int(record["patient_id"])
    if record["parent_delivery_id"] is not None:
        record["parent_delivery_id"] = int(record["parent_delivery_id"])
    record["attempt_number"] = int(record["attempt_number"])
    return record


def _validate_channel(channel: str) -> None:
    if channel not in COMMUNICATION_CHANNELS:
        raise ValueError(f"Invalid channel: {channel!r}")


def _validate_status(status: str) -> None:
    if status not in DELIVERY_STATUSES:
        raise ValueError(f"Invalid delivery status: {status!r}")


def upsert_patient_channel(
    *,
    patient_id: int,
    channel: str,
    address: str,
    enabled: bool = True,
    verified_at: str | None = None,
) -> dict[str, Any]:
    _validate_channel(channel)
    cleaned_address = address.strip()
    if not cleaned_address:
        raise ValueError("Channel address must not be empty")

    now = _utc_now()
    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id FROM patient_communication_channels
            WHERE patient_id = ? AND channel = ?
            """,
            (patient_id, channel),
        ).fetchone()

        if existing is not None:
            conn.execute(
                """
                UPDATE patient_communication_channels
                SET address = ?, enabled = ?, verified_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (cleaned_address, int(enabled), verified_at, now, int(existing["id"])),
            )
            channel_id = int(existing["id"])
        else:
            cursor = conn.execute(
                """
                INSERT INTO patient_communication_channels (
                    patient_id, channel, address, enabled, verified_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (patient_id, channel, cleaned_address, int(enabled), verified_at, now, now),
            )
            channel_id = int(cursor.lastrowid)
        conn.commit()

    return get_patient_channel(channel_id)


def get_patient_channel(channel_id: int) -> dict[str, Any]:
    columns = ", ".join(_CHANNEL_COLUMNS)
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {columns} FROM patient_communication_channels WHERE id = ?",
            (channel_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"Channel record not found: {channel_id}")
    return _row_to_channel(row)


def list_patient_channels(patient_id: int, *, enabled_only: bool = False) -> list[dict[str, Any]]:
    columns = ", ".join(_CHANNEL_COLUMNS)
    query = f"""
        SELECT {columns}
        FROM patient_communication_channels
        WHERE patient_id = ?
    """
    params: list[Any] = [patient_id]
    if enabled_only:
        query += " AND enabled = 1"
    query += " ORDER BY channel ASC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_channel(row) for row in rows]


def create_delivery_record(
    *,
    patient_id: int,
    channel: str,
    source_type: str,
    message_text: str,
    status: str,
    source_id: str | None = None,
    provider_name: str | None = None,
    provider_message_id: str | None = None,
    error_message: str | None = None,
    attempt_number: int = 1,
    parent_delivery_id: int | None = None,
) -> dict[str, Any]:
    _validate_channel(channel)
    _validate_status(status)

    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO communication_deliveries (
                patient_id,
                channel,
                source_type,
                source_id,
                message_text,
                status,
                provider_name,
                provider_message_id,
                error_message,
                attempt_number,
                parent_delivery_id,
                replied_at,
                reply_text,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
            """,
            (
                patient_id,
                channel,
                source_type,
                source_id,
                message_text.strip(),
                status,
                provider_name,
                provider_message_id,
                error_message,
                attempt_number,
                parent_delivery_id,
                now,
                now,
            ),
        )
        conn.commit()
        delivery_id = int(cursor.lastrowid)

    return get_delivery_record(delivery_id)


def update_delivery_status(
    delivery_id: int,
    *,
    status: str,
    provider_message_id: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    _validate_status(status)
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE communication_deliveries
            SET status = ?,
                provider_message_id = COALESCE(?, provider_message_id),
                error_message = COALESCE(?, error_message),
                updated_at = ?
            WHERE id = ?
            """,
            (status, provider_message_id, error_message, now, delivery_id),
        )
        conn.commit()
    return get_delivery_record(delivery_id)


def mark_delivery_replied(
    delivery_id: int,
    *,
    reply_text: str,
) -> dict[str, Any]:
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE communication_deliveries
            SET status = 'replied',
                reply_text = ?,
                replied_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (reply_text.strip(), now, now, delivery_id),
        )
        conn.commit()
    return get_delivery_record(delivery_id)


def get_delivery_record(delivery_id: int) -> dict[str, Any]:
    columns = ", ".join(_DELIVERY_COLUMNS)
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {columns} FROM communication_deliveries WHERE id = ?",
            (delivery_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"Delivery record not found: {delivery_id}")
    return _row_to_delivery(row)


def list_delivery_history(
    patient_id: int,
    *,
    source_type: str | None = None,
    source_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    columns = ", ".join(_DELIVERY_COLUMNS)
    query = f"""
        SELECT {columns}
        FROM communication_deliveries
        WHERE patient_id = ?
    """
    params: list[Any] = [patient_id]

    if source_type is not None:
        query += " AND source_type = ?"
        params.append(source_type)
    if source_id is not None:
        query += " AND source_id = ?"
        params.append(source_id)

    query += " ORDER BY id ASC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_delivery(row) for row in rows]


def list_failed_deliveries_since(since_iso: str, *, limit: int = 50) -> list[dict[str, Any]]:
    columns = ", ".join(_DELIVERY_COLUMNS)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {columns}
            FROM communication_deliveries
            WHERE status = 'failed'
              AND created_at >= ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (since_iso, limit),
        ).fetchall()
    return [_row_to_delivery(row) for row in rows]


def list_patients_without_reply(
    *,
    source_type: str = "follow_up",
    since_iso: str,
) -> list[int]:
    """Patient IDs notified but without a replied delivery for follow-ups."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT f.patient_id
            FROM follow_ups f
            WHERE f.status = 'notified'
              AND f.notified_at >= ?
              AND NOT EXISTS (
                  SELECT 1
                  FROM communication_deliveries d
                  WHERE d.patient_id = f.patient_id
                    AND d.source_type = ?
                    AND d.status = 'replied'
                    AND d.created_at >= f.notified_at
              )
            ORDER BY f.patient_id ASC
            """,
            (since_iso, source_type),
        ).fetchall()
    return [int(row["patient_id"]) for row in rows]


def get_pending_follow_up_reply_delivery(patient_id: int) -> dict[str, Any] | None:
    """Most recent follow-up delivery awaiting a patient reply."""
    columns = ", ".join(_DELIVERY_COLUMNS)
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT {columns}
            FROM communication_deliveries
            WHERE patient_id = ?
              AND source_type = 'follow_up'
              AND status IN ('sent', 'delivered')
              AND replied_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (patient_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_delivery(row)

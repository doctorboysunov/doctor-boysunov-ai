import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.connection import get_connection
from app.domain.follow_up_schedule import FOLLOW_UP_KINDS, FOLLOW_UP_STATUSES
from app.services.follow_up_scheduler import (
    build_initial_follow_up_dates,
    build_recurring_follow_up_date,
    next_recurring_sequence,
    parse_iso_date,
    to_iso_date,
)

logger = logging.getLogger("doctor_boysunov.follow_ups")

_FOLLOW_UP_COLUMNS = (
    "id",
    "patient_id",
    "treatment_id",
    "sequence_number",
    "follow_up_kind",
    "scheduled_date",
    "status",
    "invitation_text",
    "notified_at",
    "completed_at",
    "response_outcome",
    "patient_reply_text",
    "high_priority",
    "retry_count",
    "created_at",
    "updated_at",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_kind(kind: str) -> None:
    if kind not in FOLLOW_UP_KINDS:
        raise ValueError(f"Invalid follow_up_kind: {kind!r}")


def _validate_status(status: str) -> None:
    if status not in FOLLOW_UP_STATUSES:
        raise ValueError(f"Invalid follow-up status: {status!r}")


def _row_to_follow_up(row) -> dict[str, Any]:
    follow_up = {column: row[column] for column in _FOLLOW_UP_COLUMNS if column in row.keys()}
    for column in _FOLLOW_UP_COLUMNS:
        follow_up.setdefault(column, None)
    follow_up["id"] = int(follow_up["id"])
    follow_up["patient_id"] = int(follow_up["patient_id"])
    follow_up["treatment_id"] = int(follow_up["treatment_id"])
    follow_up["sequence_number"] = int(follow_up["sequence_number"])
    follow_up["high_priority"] = bool(follow_up.get("high_priority") or 0)
    follow_up["retry_count"] = int(follow_up.get("retry_count") or 0)
    follow_up.setdefault("response_outcome", "pending")
    return follow_up


def create_follow_up(
    *,
    patient_id: int,
    treatment_id: int,
    sequence_number: int,
    follow_up_kind: str,
    scheduled_date: str,
    invitation_text: str,
    status: str = "scheduled",
) -> dict[str, Any]:
    _validate_kind(follow_up_kind)
    _validate_status(status)
    parse_iso_date(scheduled_date)

    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO follow_ups (
                patient_id,
                treatment_id,
                sequence_number,
                follow_up_kind,
                scheduled_date,
                status,
                invitation_text,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                treatment_id,
                sequence_number,
                follow_up_kind,
                scheduled_date,
                status,
                invitation_text,
                now,
                now,
            ),
        )
        conn.commit()
        follow_up_id = int(cursor.lastrowid)

    follow_up = get_follow_up(follow_up_id)
    assert follow_up is not None
    return follow_up


def get_follow_up(follow_up_id: int) -> dict[str, Any] | None:
    columns = ", ".join(_FOLLOW_UP_COLUMNS)
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {columns} FROM follow_ups WHERE id = ?",
            (follow_up_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_follow_up(row)


def list_follow_ups_for_patient(
    patient_id: int,
    *,
    include_cancelled: bool = False,
) -> list[dict[str, Any]]:
    columns = ", ".join(_FOLLOW_UP_COLUMNS)
    query = f"""
            SELECT {columns}
            FROM follow_ups
            WHERE patient_id = ?
            """
    params: list[Any] = [patient_id]
    if not include_cancelled:
        query += " AND status != 'cancelled'"
    query += " ORDER BY sequence_number ASC, id ASC"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_follow_up(row) for row in rows]


def list_follow_ups_for_treatment(treatment_id: int) -> list[dict[str, Any]]:
    columns = ", ".join(_FOLLOW_UP_COLUMNS)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {columns}
            FROM follow_ups
            WHERE treatment_id = ?
            ORDER BY sequence_number ASC, id ASC
            """,
            (treatment_id,),
        ).fetchall()
    return [_row_to_follow_up(row) for row in rows]


def get_latest_follow_up_for_treatment(treatment_id: int) -> dict[str, Any] | None:
    columns = ", ".join(_FOLLOW_UP_COLUMNS)
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT {columns}
            FROM follow_ups
            WHERE treatment_id = ?
            ORDER BY sequence_number DESC, id DESC
            LIMIT 1
            """,
            (treatment_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_follow_up(row)


def list_due_follow_ups(*, as_of_date: str) -> list[dict[str, Any]]:
    parse_iso_date(as_of_date)
    columns = ", ".join(_FOLLOW_UP_COLUMNS)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {columns}
            FROM follow_ups
            WHERE status = 'scheduled'
              AND scheduled_date <= ?
            ORDER BY scheduled_date ASC, sequence_number ASC
            """,
            (as_of_date,),
        ).fetchall()
    return [_row_to_follow_up(row) for row in rows]


def list_follow_ups_due_on(scheduled_date: str) -> list[dict[str, Any]]:
    parse_iso_date(scheduled_date)
    columns = ", ".join(_FOLLOW_UP_COLUMNS)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {columns}
            FROM follow_ups
            WHERE scheduled_date = ?
              AND status IN ('scheduled', 'notified')
            ORDER BY sequence_number ASC
            """,
            (scheduled_date,),
        ).fetchall()
    return [_row_to_follow_up(row) for row in rows]


def list_follow_ups_in_range(start_date: str, end_date: str) -> list[dict[str, Any]]:
    parse_iso_date(start_date)
    parse_iso_date(end_date)
    columns = ", ".join(_FOLLOW_UP_COLUMNS)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {columns}
            FROM follow_ups
            WHERE scheduled_date >= ?
              AND scheduled_date <= ?
              AND status != 'cancelled'
            ORDER BY scheduled_date ASC, sequence_number ASC
            """,
            (start_date, end_date),
        ).fetchall()
    return [_row_to_follow_up(row) for row in rows]


def list_follow_ups_by_sequences(
    *,
    as_of_date: str,
    sequence_numbers: tuple[int, ...],
) -> list[dict[str, Any]]:
    if not sequence_numbers:
        return []
    placeholders = ", ".join("?" for _ in sequence_numbers)
    columns = ", ".join(_FOLLOW_UP_COLUMNS)
    params: list[Any] = [as_of_date, *sequence_numbers]
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {columns}
            FROM follow_ups
            WHERE scheduled_date <= ?
              AND status IN ('scheduled', 'notified')
              AND sequence_number IN ({placeholders})
            ORDER BY scheduled_date ASC, sequence_number ASC
            """,
            params,
        ).fetchall()
    return [_row_to_follow_up(row) for row in rows]


def reschedule_follow_up(follow_up_id: int, *, scheduled_date: str) -> dict[str, Any]:
    parse_iso_date(scheduled_date)
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE follow_ups
            SET scheduled_date = ?, status = 'scheduled', updated_at = ?
            WHERE id = ?
            """,
            (scheduled_date, now, follow_up_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Follow-up not found: {follow_up_id}")
    follow_up = get_follow_up(follow_up_id)
    assert follow_up is not None
    return follow_up


def mark_follow_up_notified(follow_up_id: int) -> dict[str, Any]:
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE follow_ups
            SET status = 'notified', notified_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, follow_up_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Follow-up not found: {follow_up_id}")

    follow_up = get_follow_up(follow_up_id)
    assert follow_up is not None
    return follow_up


def mark_follow_up_completed(follow_up_id: int) -> dict[str, Any]:
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE follow_ups
            SET status = 'completed', completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, follow_up_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Follow-up not found: {follow_up_id}")

    follow_up = get_follow_up(follow_up_id)
    assert follow_up is not None
    return follow_up


def count_follow_ups_for_treatment(treatment_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM follow_ups WHERE treatment_id = ?",
            (treatment_id,),
        ).fetchone()
    return int(row["count"])


def cancel_pending_follow_ups_for_treatment(treatment_id: int) -> int:
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE follow_ups
            SET status = 'cancelled', updated_at = ?
            WHERE treatment_id = ?
              AND status IN ('scheduled', 'notified')
            """,
            (now, treatment_id),
        )
        conn.commit()
    return int(cursor.rowcount)


def cancel_pending_follow_ups_for_patient(patient_id: int) -> int:
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE follow_ups
            SET status = 'cancelled', updated_at = ?
            WHERE patient_id = ?
              AND status IN ('scheduled', 'notified')
            """,
            (now, patient_id),
        )
        conn.commit()
    return int(cursor.rowcount)


def get_open_notified_follow_up(patient_id: int) -> dict[str, Any] | None:
    """Latest notified follow-up awaiting a patient reply."""
    columns = ", ".join(_FOLLOW_UP_COLUMNS)
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT {columns}
            FROM follow_ups
            WHERE patient_id = ?
              AND status = 'notified'
              AND response_outcome = 'pending'
            ORDER BY notified_at DESC, id DESC
            LIMIT 1
            """,
            (patient_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_follow_up(row)


def record_follow_up_outcome(
    follow_up_id: int,
    *,
    outcome: str,
    reply_text: str | None = None,
    high_priority: bool = False,
) -> dict[str, Any]:
    from app.domain.care_manager import CARE_OUTCOMES

    if outcome not in CARE_OUTCOMES:
        raise ValueError(f"Invalid outcome: {outcome!r}")

    now = _utc_now()
    status = "completed" if outcome in {"good", "no_change", "worse"} else "no_response"
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE follow_ups
            SET response_outcome = ?,
                patient_reply_text = ?,
                high_priority = ?,
                status = ?,
                completed_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                outcome,
                reply_text,
                1 if high_priority else 0,
                status,
                now,
                now,
                follow_up_id,
            ),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Follow-up not found: {follow_up_id}")

    follow_up = get_follow_up(follow_up_id)
    assert follow_up is not None
    return follow_up


def mark_follow_up_no_response(follow_up_id: int) -> dict[str, Any]:
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE follow_ups
            SET status = 'no_response',
                response_outcome = 'no_response',
                updated_at = ?
            WHERE id = ?
            """,
            (now, follow_up_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Follow-up not found: {follow_up_id}")
    follow_up = get_follow_up(follow_up_id)
    assert follow_up is not None
    return follow_up


def increment_follow_up_retry(follow_up_id: int) -> dict[str, Any]:
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE follow_ups
            SET retry_count = retry_count + 1,
                notified_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (now, now, follow_up_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Follow-up not found: {follow_up_id}")
    follow_up = get_follow_up(follow_up_id)
    assert follow_up is not None
    return follow_up


def list_follow_ups_needing_retry(*, as_of_date: str) -> list[dict[str, Any]]:
    """Notified follow-ups with no reply after CARE_MANAGER_RETRY_DAYS."""
    from app.domain.care_manager import CARE_MANAGER_RETRY_DAYS
    from app.services.follow_up_scheduler import parse_iso_date, to_iso_date

    as_of = parse_iso_date(as_of_date)
    cutoff = to_iso_date(as_of - timedelta(days=CARE_MANAGER_RETRY_DAYS))
    columns = ", ".join(_FOLLOW_UP_COLUMNS)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {columns}
            FROM follow_ups
            WHERE status = 'notified'
              AND response_outcome = 'pending'
              AND date(notified_at) <= ?
            ORDER BY notified_at ASC
            """,
            (cutoff,),
        ).fetchall()
    return [_row_to_follow_up(row) for row in rows]


def list_upcoming_follow_ups(*, from_date: str, limit: int = 50) -> list[dict[str, Any]]:
    parse_iso_date(from_date)
    columns = ", ".join(_FOLLOW_UP_COLUMNS)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {columns}
            FROM follow_ups
            WHERE scheduled_date >= ?
              AND status IN ('scheduled', 'notified')
            ORDER BY scheduled_date ASC, sequence_number ASC
            LIMIT ?
            """,
            (from_date, limit),
        ).fetchall()
    return [_row_to_follow_up(row) for row in rows]

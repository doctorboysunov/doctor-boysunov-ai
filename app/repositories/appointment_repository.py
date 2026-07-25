import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection
from app.domain.appointment_status import (
    APPOINTMENT_STATUSES,
    DEFAULT_APPOINTMENT_STATUS,
)

logger = logging.getLogger("doctor_boysunov.appointments")

_APPOINTMENT_COLUMNS = (
    "id",
    "patient_id",
    "doctor_name",
    "appointment_date",
    "appointment_time",
    "complaint",
    "status",
    "confirmation_time",
    "confirmed_by",
    "admin_notes",
    "created_at",
    "updated_at",
)

_APPOINTMENT_SELECT = """
    SELECT
        a.id,
        a.patient_id,
        a.doctor_name,
        a.appointment_date,
        a.appointment_time,
        a.complaint,
        a.status,
        a.confirmation_time,
        a.confirmed_by,
        a.admin_notes,
        a.created_at,
        a.updated_at,
        u.telegram_id,
        u.full_name AS telegram_full_name,
        p.full_name AS patient_full_name,
        p.phone_number
    FROM appointments a
    JOIN users u ON u.id = a.patient_id
    LEFT JOIN patient_profiles p ON p.user_id = a.patient_id
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_appointment(row) -> dict[str, Any]:
    appointment = {column: row[column] for column in _APPOINTMENT_COLUMNS}
    appointment["id"] = int(appointment["id"])
    appointment["patient_id"] = int(appointment["patient_id"])
    return appointment


def _row_to_appointment_with_patient(row) -> dict[str, Any]:
    appointment = _row_to_appointment(row)
    raw_telegram_id = row["telegram_id"]
    appointment["telegram_id"] = int(raw_telegram_id) if raw_telegram_id is not None else None
    appointment["telegram_full_name"] = row["telegram_full_name"]
    appointment["patient_full_name"] = row["patient_full_name"]
    appointment["phone_number"] = row["phone_number"]
    return appointment


def _validate_status(status: str) -> None:
    if status not in APPOINTMENT_STATUSES:
        raise ValueError(f"Invalid appointment status: {status!r}")


def _fetch_one_appointment(where_clause: str, params: tuple) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            f"{_APPOINTMENT_SELECT} {where_clause}",
            params,
        ).fetchone()
    if row is None:
        return None
    return _row_to_appointment_with_patient(row)


def _fetch_appointments(where_clause: str, params: tuple) -> list[dict[str, Any]]:
    where_sql = where_clause or "WHERE 1=1"
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            {_APPOINTMENT_SELECT}
            {where_sql}
            ORDER BY a.id DESC
            """,
            params,
        ).fetchall()
    return [_row_to_appointment_with_patient(row) for row in rows]


def create_appointment(
    *,
    patient_id: int,
    doctor_name: str,
    appointment_date: str,
    appointment_time: str,
    complaint: str,
    status: str = DEFAULT_APPOINTMENT_STATUS,
) -> dict[str, Any]:
    _validate_status(status)

    for field_name, value in (
        ("doctor_name", doctor_name),
        ("appointment_date", appointment_date),
        ("appointment_time", appointment_time),
        ("complaint", complaint),
    ):
        if not str(value).strip():
            raise ValueError(f"{field_name} must not be empty")

    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO appointments (
                patient_id,
                doctor_name,
                appointment_date,
                appointment_time,
                complaint,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                doctor_name.strip(),
                appointment_date.strip(),
                appointment_time.strip(),
                complaint.strip(),
                status,
                now,
                now,
            ),
        )
        conn.commit()
        appointment_id = int(cursor.lastrowid)

    logger.info(
        "create_appointment patient_id=%s appointment_id=%s status=%s",
        patient_id,
        appointment_id,
        status,
    )
    appointment = get_appointment(appointment_id)
    assert appointment is not None
    return appointment


def get_appointment(appointment_id: int) -> dict[str, Any] | None:
    return _fetch_one_appointment("WHERE a.id = ?", (appointment_id,))


def get_patient_appointments(patient_id: int) -> list[dict[str, Any]]:
    return _fetch_appointments("WHERE a.patient_id = ?", (patient_id,))


def list_appointments() -> list[dict[str, Any]]:
    return _fetch_appointments("", ())


def list_appointments_by_status(status: str) -> list[dict[str, Any]]:
    _validate_status(status)
    return _fetch_appointments("WHERE a.status = ?", (status,))


def list_appointments_for_date(appointment_date: str) -> list[dict[str, Any]]:
    return _fetch_appointments("WHERE a.appointment_date = ?", (appointment_date.strip(),))


def list_appointments_in_range(start_date: str, end_date: str) -> list[dict[str, Any]]:
    return _fetch_appointments(
        "WHERE a.appointment_date >= ? AND a.appointment_date <= ?",
        (start_date.strip(), end_date.strip()),
    )


def list_upcoming_appointments(*, from_date: str) -> list[dict[str, Any]]:
    return _fetch_appointments(
        "WHERE a.appointment_date >= ? AND a.status != 'cancelled'",
        (from_date.strip(),),
    )


def list_missed_appointments(*, before_date: str) -> list[dict[str, Any]]:
    return _fetch_appointments(
        """
        WHERE a.appointment_date < ?
          AND a.status IN ('pending', 'confirmed')
        """,
        (before_date.strip(),),
    )


def update_status(appointment_id: int, status: str) -> dict[str, Any]:
    _validate_status(status)
    now = _utc_now()

    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE appointments
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, now, appointment_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Appointment not found: {appointment_id}")

    logger.info("update_status appointment_id=%s status=%s", appointment_id, status)
    appointment = get_appointment(appointment_id)
    assert appointment is not None
    return appointment


def confirm_appointment(appointment_id: int, *, confirmed_by: str) -> dict[str, Any]:
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE appointments
            SET
                status = 'confirmed',
                confirmation_time = ?,
                confirmed_by = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (now, confirmed_by.strip(), now, appointment_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Appointment not found: {appointment_id}")

    logger.info(
        "confirm_appointment appointment_id=%s confirmed_by=%s",
        appointment_id,
        confirmed_by,
    )
    appointment = get_appointment(appointment_id)
    assert appointment is not None
    return appointment


def reschedule_appointment(
    appointment_id: int,
    *,
    appointment_date: str,
    appointment_time: str,
    updated_by: str | None = None,
) -> dict[str, Any]:
    if not appointment_date.strip() or not appointment_time.strip():
        raise ValueError("appointment_date and appointment_time must not be empty")

    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE appointments
            SET
                appointment_date = ?,
                appointment_time = ?,
                updated_at = ?,
                confirmed_by = COALESCE(?, confirmed_by)
            WHERE id = ?
            """,
            (
                appointment_date.strip(),
                appointment_time.strip(),
                now,
                updated_by.strip() if updated_by else None,
                appointment_id,
            ),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Appointment not found: {appointment_id}")

    logger.info(
        "reschedule_appointment appointment_id=%s date=%s time=%s",
        appointment_id,
        appointment_date,
        appointment_time,
    )
    appointment = get_appointment(appointment_id)
    assert appointment is not None
    return appointment


def add_admin_notes(
    appointment_id: int,
    notes: str,
    *,
    updated_by: str | None = None,
) -> dict[str, Any]:
    if not notes.strip():
        raise ValueError("notes must not be empty")

    existing = get_appointment(appointment_id)
    if existing is None:
        raise ValueError(f"Appointment not found: {appointment_id}")

    combined = notes.strip()
    if existing.get("admin_notes"):
        combined = f"{existing['admin_notes']}\n{notes.strip()}"

    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE appointments
            SET
                admin_notes = ?,
                updated_at = ?,
                confirmed_by = COALESCE(?, confirmed_by)
            WHERE id = ?
            """,
            (combined, now, updated_by.strip() if updated_by else None, appointment_id),
        )
        conn.commit()

    logger.info("add_admin_notes appointment_id=%s", appointment_id)
    appointment = get_appointment(appointment_id)
    assert appointment is not None
    return appointment


def cancel_appointment(appointment_id: int, *, cancelled_by: str | None = None) -> dict[str, Any]:
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE appointments
            SET
                status = 'cancelled',
                updated_at = ?,
                confirmed_by = COALESCE(?, confirmed_by)
            WHERE id = ?
            """,
            (now, cancelled_by.strip() if cancelled_by else None, appointment_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Appointment not found: {appointment_id}")

    logger.info("cancel_appointment appointment_id=%s", appointment_id)
    appointment = get_appointment(appointment_id)
    assert appointment is not None
    return appointment

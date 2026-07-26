import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection
from app.services.follow_up_scheduler import parse_iso_date, to_iso_date

logger = logging.getLogger("doctor_boysunov.treatments")

_TREATMENT_COLUMNS = (
    "id",
    "patient_id",
    "started_at",
    "status",
    "created_at",
    "updated_at",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_treatment(row) -> dict[str, Any]:
    treatment = {column: row[column] for column in _TREATMENT_COLUMNS}
    treatment["id"] = int(treatment["id"])
    treatment["patient_id"] = int(treatment["patient_id"])
    return treatment


def create_treatment(*, patient_id: int, started_at: str, status: str = "active") -> dict[str, Any]:
    if status not in {"active", "completed", "cancelled"}:
        raise ValueError(f"Invalid treatment status: {status!r}")
    parse_iso_date(started_at)

    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO patient_treatments (
                patient_id, started_at, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (patient_id, started_at, status, now, now),
        )
        conn.commit()
        treatment_id = int(cursor.lastrowid)

    logger.info("create_treatment patient_id=%s treatment_id=%s", patient_id, treatment_id)
    treatment = get_treatment(treatment_id)
    assert treatment is not None
    return treatment


def get_treatment(treatment_id: int) -> dict[str, Any] | None:
    columns = ", ".join(_TREATMENT_COLUMNS)
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {columns} FROM patient_treatments WHERE id = ?",
            (treatment_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_treatment(row)


def get_active_treatment(patient_id: int) -> dict[str, Any] | None:
    columns = ", ".join(_TREATMENT_COLUMNS)
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT {columns}
            FROM patient_treatments
            WHERE patient_id = ? AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """,
            (patient_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_treatment(row)


def list_treatments_for_patient(patient_id: int) -> list[dict[str, Any]]:
    columns = ", ".join(_TREATMENT_COLUMNS)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {columns}
            FROM patient_treatments
            WHERE patient_id = ?
            ORDER BY id DESC
            """,
            (patient_id,),
        ).fetchall()
    return [_row_to_treatment(row) for row in rows]


def update_treatment_status(treatment_id: int, *, status: str) -> dict[str, Any]:
    if status not in {"active", "completed", "cancelled"}:
        raise ValueError(f"Invalid treatment status: {status!r}")

    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE patient_treatments
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, now, treatment_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Treatment not found: {treatment_id}")

    treatment = get_treatment(treatment_id)
    assert treatment is not None
    return treatment


def complete_active_treatment(patient_id: int) -> dict[str, Any] | None:
    active = get_active_treatment(patient_id)
    if active is None:
        return None
    return update_treatment_status(int(active["id"]), status="completed")


def cancel_active_treatment(patient_id: int) -> dict[str, Any] | None:
    active = get_active_treatment(patient_id)
    if active is None:
        return None
    return update_treatment_status(int(active["id"]), status="cancelled")

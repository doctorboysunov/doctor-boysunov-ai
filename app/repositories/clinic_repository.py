"""Clinic location persistence — admin-configurable."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection
from app.domain.clinic import CLINIC_ROLES

logger = logging.getLogger("doctor_boysunov.clinic")

_CLINIC_COLUMNS = (
    "id",
    "clinic_name",
    "staff_name",
    "role",
    "specialty",
    "address",
    "google_maps_link",
    "latitude",
    "longitude",
    "working_days",
    "working_hours_start",
    "working_hours_end",
    "phone",
    "services",
    "is_active",
    "sort_priority",
    "created_at",
    "updated_at",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_clinic(row) -> dict[str, Any]:
    clinic = {column: row[column] for column in _CLINIC_COLUMNS if column in row.keys()}
    for column in _CLINIC_COLUMNS:
        clinic.setdefault(column, None)
    clinic["id"] = int(clinic["id"])
    clinic["is_active"] = bool(clinic.get("is_active", 1))
    clinic["sort_priority"] = int(clinic.get("sort_priority") or 100)
    clinic["latitude"] = float(clinic["latitude"])
    clinic["longitude"] = float(clinic["longitude"])
    return clinic


def _validate_role(role: str) -> None:
    if role not in CLINIC_ROLES:
        raise ValueError(f"Invalid clinic role: {role!r}")


def create_clinic_location(
    *,
    clinic_name: str,
    staff_name: str,
    role: str,
    address: str,
    latitude: float,
    longitude: float,
    specialty: str | None = None,
    google_maps_link: str | None = None,
    working_days: str = "mon,tue,wed,thu,fri",
    working_hours_start: str = "09:00",
    working_hours_end: str = "18:00",
    phone: str | None = None,
    services: str | None = None,
    sort_priority: int = 100,
    is_active: bool = True,
) -> dict[str, Any]:
    _validate_role(role)
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO clinic_locations (
                clinic_name, staff_name, role, specialty, address,
                google_maps_link, latitude, longitude, working_days,
                working_hours_start, working_hours_end, phone, services,
                is_active, sort_priority, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clinic_name,
                staff_name,
                role,
                specialty,
                address,
                google_maps_link,
                latitude,
                longitude,
                working_days,
                working_hours_start,
                working_hours_end,
                phone,
                services,
                1 if is_active else 0,
                sort_priority,
                now,
                now,
            ),
        )
        clinic_id = int(cursor.lastrowid)
        row = conn.execute(
            "SELECT * FROM clinic_locations WHERE id = ?",
            (clinic_id,),
        ).fetchone()
        conn.commit()
    return _row_to_clinic(row)


def get_clinic_location(clinic_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clinic_locations WHERE id = ?",
            (clinic_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_clinic(row)


def list_clinic_locations(*, active_only: bool = True) -> list[dict[str, Any]]:
    query = "SELECT * FROM clinic_locations"
    params: list[Any] = []
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY sort_priority ASC, role ASC, id ASC"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_clinic(row) for row in rows]


def update_clinic_location(clinic_id: int, **fields: Any) -> dict[str, Any] | None:
    existing = get_clinic_location(clinic_id)
    if existing is None:
        return None

    if "role" in fields and fields["role"] is not None:
        _validate_role(fields["role"])

    allowed = {
        "clinic_name",
        "staff_name",
        "role",
        "specialty",
        "address",
        "google_maps_link",
        "latitude",
        "longitude",
        "working_days",
        "working_hours_start",
        "working_hours_end",
        "phone",
        "services",
        "sort_priority",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if "is_active" in fields and fields["is_active"] is not None:
        updates["is_active"] = 1 if fields["is_active"] else 0

    if not updates:
        return existing

    updates["updated_at"] = _utc_now()
    set_clause = ", ".join(f"{column} = ?" for column in updates)
    params = list(updates.values()) + [clinic_id]

    with get_connection() as conn:
        conn.execute(
            f"UPDATE clinic_locations SET {set_clause} WHERE id = ?",
            params,
        )
        row = conn.execute(
            "SELECT * FROM clinic_locations WHERE id = ?",
            (clinic_id,),
        ).fetchone()
        conn.commit()
    return _row_to_clinic(row)


def deactivate_clinic_location(clinic_id: int) -> dict[str, Any] | None:
    return update_clinic_location(clinic_id, is_active=False)

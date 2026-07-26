"""Persisted admin session including explicit patient registration mode."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.connection import get_connection

logger = logging.getLogger("doctor_boysunov.admin_session")

VALID_MODES = frozenset({"normal_ai", "doctor_visit", "patient_registration"})
REGISTRATION_TIMEOUT_MINUTES = 15


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def get_admin_session(admin_telegram_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT admin_telegram_id, mode, active_patient_id, active_patient_name,
                   visit_id, registration_started_at, updated_at
            FROM admin_sessions
            WHERE admin_telegram_id = ?
            """,
            (admin_telegram_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "admin_telegram_id": int(row["admin_telegram_id"]),
        "mode": row["mode"],
        "active_patient_id": int(row["active_patient_id"]) if row["active_patient_id"] is not None else None,
        "active_patient_name": row["active_patient_name"],
        "visit_id": int(row["visit_id"]) if row["visit_id"] is not None else None,
        "registration_started_at": row["registration_started_at"],
        "updated_at": row["updated_at"],
    }


def upsert_admin_session(
    admin_telegram_id: int,
    *,
    mode: str,
    active_patient_id: int | None = None,
    active_patient_name: str | None = None,
    visit_id: int | None = None,
    registration_started_at: str | None = None,
) -> dict[str, Any]:
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid admin session mode: {mode!r}")

    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO admin_sessions (
                admin_telegram_id, mode, active_patient_id, active_patient_name,
                visit_id, registration_started_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(admin_telegram_id) DO UPDATE SET
                mode = excluded.mode,
                active_patient_id = excluded.active_patient_id,
                active_patient_name = excluded.active_patient_name,
                visit_id = excluded.visit_id,
                registration_started_at = excluded.registration_started_at,
                updated_at = excluded.updated_at
            """,
            (
                admin_telegram_id,
                mode,
                active_patient_id,
                active_patient_name,
                visit_id,
                registration_started_at,
                now,
            ),
        )
        conn.commit()
    session = get_admin_session(admin_telegram_id)
    logger.info(
        "admin_session_updated telegram_id=%s mode=%s active_patient_id=%s",
        admin_telegram_id,
        mode,
        active_patient_id,
    )
    return session or {}


def start_patient_registration_mode(admin_telegram_id: int) -> dict[str, Any]:
    now = _utc_now()
    return upsert_admin_session(
        admin_telegram_id,
        mode="patient_registration",
        registration_started_at=now,
    )


def complete_patient_creation_session(
    admin_telegram_id: int,
    *,
    patient_id: int,
    patient_name: str,
    visit_id: int | None = None,
) -> dict[str, Any]:
    """Exit Patient Registration and enter normal AI assistant mode."""
    return upsert_admin_session(
        admin_telegram_id,
        mode="normal_ai",
        active_patient_id=patient_id,
        active_patient_name=patient_name,
        visit_id=visit_id,
        registration_started_at=None,
    )


def clear_patient_registration_mode(admin_telegram_id: int) -> dict[str, Any] | None:
    existing = get_admin_session(admin_telegram_id)
    if existing is None:
        return None
    return upsert_admin_session(
        admin_telegram_id,
        mode="normal_ai",
        active_patient_id=existing.get("active_patient_id"),
        active_patient_name=existing.get("active_patient_name"),
        visit_id=existing.get("visit_id"),
        registration_started_at=None,
    )


def expire_stale_registration_mode(
    admin_telegram_id: int,
    *,
    timeout_minutes: int = REGISTRATION_TIMEOUT_MINUTES,
) -> bool:
    """Clear expired patient registration mode. Returns True if expired."""
    session = get_admin_session(admin_telegram_id)
    if session is None or session["mode"] != "patient_registration":
        return False

    started = _parse_iso(session.get("registration_started_at"))
    if started is None:
        clear_patient_registration_mode(admin_telegram_id)
        return True

    if datetime.now(timezone.utc) - started > timedelta(minutes=timeout_minutes):
        clear_patient_registration_mode(admin_telegram_id)
        logger.info("admin_registration_expired telegram_id=%s", admin_telegram_id)
        return True
    return False


def expire_all_stale_registration_modes(
    *,
    timeout_minutes: int = REGISTRATION_TIMEOUT_MINUTES,
) -> int:
    """Clear expired registration sessions. Returns count cleared."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT admin_telegram_id FROM admin_sessions WHERE mode = 'patient_registration'"
        ).fetchall()
    cleared = 0
    for row in rows:
        if expire_stale_registration_mode(
            int(row["admin_telegram_id"]),
            timeout_minutes=timeout_minutes,
        ):
            cleared += 1
    return cleared


def is_patient_registration_mode_active(admin_telegram_id: int) -> bool:
    expire_stale_registration_mode(admin_telegram_id)
    session = get_admin_session(admin_telegram_id)
    return session is not None and session["mode"] == "patient_registration"

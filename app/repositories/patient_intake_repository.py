"""Persistent patient capture with phone-based deduplication."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection
from app.repositories.patient_profile_repository import (
    get_or_create_patient_profile,
    get_patient_profile,
    update_patient_profile,
)
from app.services.patient_intake.phone import normalize_phone

logger = logging.getLogger("doctor_boysunov.patient_intake")

CAPTURE_SOURCES = ("telegram", "web", "mobile", "voice", "contact", "ocr")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _telegram_id_nullable(conn) -> bool:
    for row in conn.execute("PRAGMA table_info(users)").fetchall():
        if row[1] == "telegram_id" and row[3] == 0:
            return True
    return False


def _allocate_telegram_id(conn, *, normalized_phone: str, telegram_id: int | None) -> int | None:
    if telegram_id is not None:
        return telegram_id
    if _telegram_id_nullable(conn):
        return None

    synthetic = -abs(hash(normalized_phone)) % (10**14)
    if synthetic == 0:
        synthetic = -1
    while conn.execute(
        "SELECT 1 FROM users WHERE telegram_id = ?",
        (synthetic,),
    ).fetchone():
        synthetic -= 1
    return synthetic


def find_patient_by_phone(phone_number: str) -> dict[str, Any] | None:
    normalized = normalize_phone(phone_number)
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT user_id
            FROM patient_profiles
            WHERE phone_normalized = ?
            LIMIT 1
            """,
            (normalized,),
        ).fetchone()

    if row is None:
        return None

    profile = get_patient_profile(int(row["user_id"]))
    if profile is None:
        return None
    return profile


def search_patients(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Find patients by phone fragment or name (case-insensitive)."""
    cleaned = query.strip()
    if not cleaned:
        return []

    phone_query: str | None = None
    try:
        phone_query = normalize_phone(cleaned)
    except ValueError:
        phone_query = None

    name_pattern = f"%{cleaned.lower()}%"
    params: list[Any] = []
    conditions: list[str] = []

    if phone_query:
        conditions.append("phone_normalized LIKE ?")
        params.append(f"%{phone_query.lstrip('+')}%")

    conditions.append("LOWER(COALESCE(full_name, '')) LIKE ?")
    params.append(name_pattern)

    where_clause = " OR ".join(conditions)
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT user_id
            FROM patient_profiles
            WHERE {where_clause}
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        profile = get_patient_profile(int(row["user_id"]))
        if profile is not None:
            results.append(profile)
    return results


def list_new_patients_since(since_date: str, *, until_date: str | None = None) -> list[dict[str, Any]]:
    """Patients registered on or after since_date (YYYY-MM-DD)."""
    params: list[Any] = [f"{since_date}T00:00:00"]
    query = """
        SELECT u.id AS user_id, u.registration_source, u.created_at,
               p.full_name, p.phone_number
        FROM users u
        LEFT JOIN patient_profiles p ON p.user_id = u.id
        WHERE u.created_at >= ?
    """
    if until_date is not None:
        query += " AND u.created_at <= ?"
        params.append(f"{until_date}T23:59:59")
    query += " ORDER BY u.created_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        {
            "patient_id": int(row["user_id"]),
            "full_name": row["full_name"],
            "phone_number": row["phone_number"],
            "registration_source": row["registration_source"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_patient_card(patient_id: int) -> dict[str, Any] | None:
    profile = get_patient_profile(patient_id)
    if profile is None:
        return None
    record = get_capture_record(patient_id)
    return {
        "patient_id": patient_id,
        "full_name": profile.get("full_name"),
        "phone_number": profile.get("phone_number"),
        "email": profile.get("email"),
        "mobile_push_token": profile.get("mobile_push_token"),
        "registration_source": record.get("registration_source"),
        "created_at": record.get("created_at"),
        "country": profile.get("country"),
        "region": profile.get("region"),
        "district": profile.get("district"),
    }


def create_captured_patient(
    *,
    full_name: str,
    phone_number: str,
    source: str,
    telegram_id: int | None = None,
    username: str | None = None,
) -> dict[str, Any]:
    if source not in CAPTURE_SOURCES:
        raise ValueError(f"Invalid capture source: {source!r}")

    normalized = normalize_phone(phone_number)
    now = _utc_now()

    with get_connection() as conn:
        if telegram_id is not None:
            existing_user = conn.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
            if existing_user is not None:
                user_id = int(existing_user["id"])
                conn.execute(
                    """
                    UPDATE users
                    SET full_name = ?, registration_source = ?
                    WHERE id = ?
                    """,
                    (full_name, source, user_id),
                )
                conn.commit()
                return update_patient_profile(
                    user_id,
                    full_name=full_name,
                    phone_number=normalized,
                )

        resolved_telegram_id = _allocate_telegram_id(
            conn,
            normalized_phone=normalized,
            telegram_id=telegram_id,
        )
        cursor = conn.execute(
            """
            INSERT INTO users (
                telegram_id,
                username,
                full_name,
                registration_source,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (resolved_telegram_id, username, full_name, source, now),
        )
        conn.commit()
        user_id = int(cursor.lastrowid)

    get_or_create_patient_profile(user_id)
    profile = update_patient_profile(
        user_id,
        full_name=full_name,
        phone_number=normalized,
    )
    from app.services.communication.channels import sync_patient_channels

    sync_patient_channels(user_id)
    logger.info(
        "create_captured_patient user_id=%s source=%s phone=%s",
        user_id,
        source,
        normalized,
    )
    return profile


def get_capture_record(patient_id: int) -> dict[str, Any]:
    profile = get_patient_profile(patient_id)
    if profile is None:
        raise ValueError(f"Patient not found: {patient_id}")

    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT id, telegram_id, registration_source, created_at
            FROM users
            WHERE id = ?
            """,
            (patient_id,),
        ).fetchone()

    return {
        "patient_id": patient_id,
        "full_name": profile.get("full_name"),
        "phone_number": profile.get("phone_number"),
        "phone_normalized": profile.get("phone_normalized"),
        "registration_source": user["registration_source"] if user else None,
        "telegram_id": user["telegram_id"] if user else None,
        "created_at": user["created_at"] if user else profile.get("created_at"),
    }

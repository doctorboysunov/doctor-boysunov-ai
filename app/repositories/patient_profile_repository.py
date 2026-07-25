import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection
from app.domain.patient_profile_fields import LIST_MERGE_FIELDS, PROFILE_FIELDS

logger = logging.getLogger("doctor_boysunov.patient_profile")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _merge_list_field(existing: str | None, new_value: str) -> str:
    items: list[str] = []
    for source in (existing, new_value):
        if not source:
            continue
        for part in source.split(","):
            cleaned = part.strip()
            if cleaned and cleaned.lower() not in {item.lower() for item in items}:
                items.append(cleaned)
    return ", ".join(items)


def _row_to_profile(row) -> dict[str, Any]:
    return {field: row[field] for field in ("id", "user_id", *PROFILE_FIELDS, "created_at", "updated_at")}


def get_patient_profile(user_id: int) -> dict[str, Any] | None:
    columns = ", ".join(("id", "user_id", *PROFILE_FIELDS, "created_at", "updated_at"))
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {columns} FROM patient_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    if row is None:
        logger.debug("get_patient_profile user_id=%s -> None", user_id)
        return None

    profile = _row_to_profile(row)
    profile["id"] = int(profile["id"])
    profile["user_id"] = int(profile["user_id"])
    logger.debug("get_patient_profile user_id=%s -> profile_id=%s", user_id, profile["id"])
    return profile


def get_or_create_patient_profile(user_id: int) -> dict[str, Any]:
    existing = get_patient_profile(user_id)
    if existing is not None:
        return existing

    now = _utc_now()
    nulls = ", ".join("NULL" for _ in PROFILE_FIELDS)
    with get_connection() as conn:
        cursor = conn.execute(
            f"""
            INSERT INTO patient_profiles (
                user_id, {", ".join(PROFILE_FIELDS)}, created_at, updated_at
            )
            VALUES (?, {nulls}, ?, ?)
            """,
            (user_id, now, now),
        )
        conn.commit()
        profile_id = int(cursor.lastrowid)

    logger.info(
        "get_or_create_patient_profile created user_id=%s profile_id=%s",
        user_id,
        profile_id,
    )
    profile = get_patient_profile(user_id)
    assert profile is not None
    return profile


def update_patient_profile(user_id: int, **fields: Any) -> dict[str, Any]:
    unknown = set(fields) - set(PROFILE_FIELDS)
    if unknown:
        raise ValueError(f"Unknown profile fields: {sorted(unknown)}")

    updates = {key: value for key, value in fields.items() if value is not None}
    if not updates:
        return get_or_create_patient_profile(user_id)

    if "age" in updates:
        age = updates["age"]
        if not isinstance(age, int) or age < 0 or age > 150:
            raise ValueError(f"Invalid age: {age!r}")

    for numeric_field, max_value in (("height_cm", 300), ("weight_kg", 500)):
        if numeric_field in updates:
            value = updates[numeric_field]
            if not isinstance(value, int) or value <= 0 or value > max_value:
                raise ValueError(f"Invalid {numeric_field}: {value!r}")

    profile = get_or_create_patient_profile(user_id)
    for field in LIST_MERGE_FIELDS:
        if field in updates:
            updates[field] = _merge_list_field(profile.get(field), str(updates[field]))

    set_clause = ", ".join(f"{column} = ?" for column in updates)
    params = list(updates.values()) + [_utc_now(), user_id]

    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE patient_profiles
            SET {set_clause}, updated_at = ?
            WHERE user_id = ?
            """,
            params,
        )
        conn.commit()

    logger.info(
        "update_patient_profile user_id=%s fields=%s",
        user_id,
        sorted(updates),
    )
    updated = get_patient_profile(user_id)
    assert updated is not None
    return updated

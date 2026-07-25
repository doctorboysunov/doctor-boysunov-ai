import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection
from app.domain.patient_file_types import FILE_CATEGORIES

logger = logging.getLogger("doctor_boysunov.patient_files")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_file(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "medical_history_id": int(row["medical_history_id"]),
        "file_name": row["file_name"],
        "stored_path": row["stored_path"],
        "mime_type": row["mime_type"],
        "file_category": row["file_category"],
        "telegram_file_id": row["telegram_file_id"],
        "caption": row["caption"],
        "created_at": row["created_at"],
    }


def _validate_file_category(file_category: str) -> None:
    if file_category not in FILE_CATEGORIES:
        raise ValueError(f"Invalid file_category: {file_category!r}")


def add_patient_file(
    user_id: int,
    medical_history_id: int,
    *,
    file_name: str,
    stored_path: str,
    file_category: str,
    mime_type: str | None = None,
    telegram_file_id: str | None = None,
    caption: str | None = None,
) -> dict[str, Any]:
    _validate_file_category(file_category)
    now = _utc_now()

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO patient_files (
                user_id, medical_history_id, file_name, stored_path,
                mime_type, file_category, telegram_file_id, caption, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                medical_history_id,
                file_name,
                stored_path,
                mime_type,
                file_category,
                telegram_file_id,
                caption,
                now,
            ),
        )
        conn.commit()
        file_id = int(cursor.lastrowid)

    logger.info(
        "add_patient_file user_id=%s file_id=%s history_id=%s category=%s",
        user_id,
        file_id,
        medical_history_id,
        file_category,
    )
    return get_patient_file(file_id)


def get_patient_file(file_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, medical_history_id, file_name, stored_path,
                   mime_type, file_category, telegram_file_id, caption, created_at
            FROM patient_files
            WHERE id = ?
            """,
            (file_id,),
        ).fetchone()

    if row is None:
        raise ValueError(f"Patient file not found: id={file_id}")

    return _row_to_file(row)


def get_patient_files(
    user_id: int,
    *,
    file_category: str | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT id, user_id, medical_history_id, file_name, stored_path,
               mime_type, file_category, telegram_file_id, caption, created_at
        FROM patient_files
        WHERE user_id = ?
    """
    params: list[Any] = [user_id]

    if file_category is not None:
        _validate_file_category(file_category)
        query += " AND file_category = ?"
        params.append(file_category)

    query += " ORDER BY id ASC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_file(row) for row in rows]


def get_patient_file_for_history(medical_history_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, medical_history_id, file_name, stored_path,
                   mime_type, file_category, telegram_file_id, caption, created_at
            FROM patient_files
            WHERE medical_history_id = ?
            """,
            (medical_history_id,),
        ).fetchone()

    if row is None:
        return None

    return _row_to_file(row)

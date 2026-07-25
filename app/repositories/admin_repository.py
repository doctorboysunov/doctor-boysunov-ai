"""Persistent administrator Telegram ID registry."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.db.connection import get_connection

logger = logging.getLogger("doctor_boysunov.admin_repository")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_admin_telegram_id(telegram_id: int, *, source: str = "env") -> None:
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO admin_telegram_ids (telegram_id, source, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO NOTHING
            """,
            (telegram_id, source, now),
        )
        conn.commit()
    logger.info("add_admin_telegram_id telegram_id=%s source=%s", telegram_id, source)


def list_admin_telegram_ids() -> tuple[int, ...]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT telegram_id FROM admin_telegram_ids ORDER BY telegram_id ASC"
        ).fetchall()
    return tuple(int(row["telegram_id"]) for row in rows)


def is_registered_admin(telegram_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM admin_telegram_ids WHERE telegram_id = ? LIMIT 1",
            (telegram_id,),
        ).fetchone()
    return row is not None


def seed_admin_ids_from_env(env_ids: tuple[int, ...]) -> int:
    added = 0
    for telegram_id in env_ids:
        before = list_admin_telegram_ids()
        add_admin_telegram_id(telegram_id, source="env")
        if telegram_id not in before:
            added += 1
    return added

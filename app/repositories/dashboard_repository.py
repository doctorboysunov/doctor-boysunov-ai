"""Dashboard snapshot persistence."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection

logger = logging.getLogger("doctor_boysunov.dashboard")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_dashboard_snapshot(
    *,
    snapshot_date: str,
    period: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    now = _utc_now()
    payload_json = json.dumps(payload, ensure_ascii=False)
    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id FROM dashboard_snapshots
            WHERE snapshot_date = ? AND period = ?
            """,
            (snapshot_date, period),
        ).fetchone()
        if existing is not None:
            conn.execute(
                """
                UPDATE dashboard_snapshots
                SET payload_json = ?, created_at = ?
                WHERE id = ?
                """,
                (payload_json, now, int(existing["id"])),
            )
            snapshot_id = int(existing["id"])
        else:
            cursor = conn.execute(
                """
                INSERT INTO dashboard_snapshots (
                    snapshot_date, period, payload_json, created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (snapshot_date, period, payload_json, now),
            )
            snapshot_id = int(cursor.lastrowid)
        conn.commit()
    return get_dashboard_snapshot(snapshot_id)


def get_dashboard_snapshot(snapshot_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, snapshot_date, period, payload_json, created_at
            FROM dashboard_snapshots
            WHERE id = ?
            """,
            (snapshot_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"Dashboard snapshot not found: {snapshot_id}")
    return {
        "id": int(row["id"]),
        "snapshot_date": row["snapshot_date"],
        "period": row["period"],
        "payload": json.loads(row["payload_json"]),
        "created_at": row["created_at"],
    }


def get_latest_dashboard_snapshot(*, snapshot_date: str, period: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, snapshot_date, period, payload_json, created_at
            FROM dashboard_snapshots
            WHERE snapshot_date = ? AND period = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (snapshot_date, period),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "snapshot_date": row["snapshot_date"],
        "period": row["period"],
        "payload": json.loads(row["payload_json"]),
        "created_at": row["created_at"],
    }

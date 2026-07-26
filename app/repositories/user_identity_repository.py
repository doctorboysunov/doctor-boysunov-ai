"""Multi-channel user identity resolution."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection
from app.domain.channels import ChannelType, DEFAULT_CHANNEL, is_supported_channel

logger = logging.getLogger("doctor_boysunov.identity")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_user_id(channel: str, external_id: str) -> int | None:
    if not is_supported_channel(channel):
        raise ValueError(f"Unsupported channel: {channel}")

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT user_id FROM user_channel_identities
            WHERE channel = ? AND external_id = ?
            """,
            (channel, external_id),
        ).fetchone()
    if row is None:
        return None
    return int(row["user_id"])


def upsert_channel_identity(
    channel: ChannelType,
    external_id: str,
    *,
    user_id: int | None = None,
    display_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
    if not is_supported_channel(channel):
        raise ValueError(f"Unsupported channel: {channel}")
    if not external_id.strip():
        raise ValueError("external_id must not be empty")

    now = _utc_now()
    metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT user_id FROM user_channel_identities
            WHERE channel = ? AND external_id = ?
            """,
            (channel, external_id),
        ).fetchone()

        if existing is not None:
            resolved_user_id = int(existing["user_id"])
            conn.execute(
                """
                UPDATE user_channel_identities
                SET display_name = COALESCE(?, display_name),
                    metadata_json = COALESCE(?, metadata_json),
                    updated_at = ?
                WHERE channel = ? AND external_id = ?
                """,
                (display_name, metadata_json, now, channel, external_id),
            )
            conn.commit()
            return resolved_user_id

        if user_id is None:
            registration_source = channel if channel != DEFAULT_CHANNEL else "telegram"
            if channel == "telegram":
                cursor = conn.execute(
                    """
                    INSERT INTO users (telegram_id, username, full_name, registration_source, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        int(external_id),
                        None,
                        display_name,
                        registration_source,
                        now,
                    ),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO users (telegram_id, username, full_name, registration_source, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (None, None, display_name, registration_source, now),
                )
            user_id = int(cursor.lastrowid)

        conn.execute(
            """
            INSERT INTO user_channel_identities (
                user_id, channel, external_id, display_name, metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, channel, external_id, display_name, metadata_json, now, now),
        )
        conn.commit()

    logger.info(
        "upsert_channel_identity channel=%s external_id=%s user_id=%s",
        channel,
        external_id,
        user_id,
    )
    return user_id


def list_user_channels(user_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT channel, external_id, display_name, metadata_json, created_at, updated_at
            FROM user_channel_identities
            WHERE user_id = ?
            ORDER BY channel ASC
            """,
            (user_id,),
        ).fetchall()

    return [
        {
            "channel": row["channel"],
            "external_id": row["external_id"],
            "display_name": row["display_name"],
            "metadata_json": row["metadata_json"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]

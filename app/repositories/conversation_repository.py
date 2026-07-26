import json
import logging
from datetime import datetime, timezone

from app.db.connection import get_connection

logger = logging.getLogger("doctor_boysunov.repository")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_user(
    telegram_id: int,
    username: str | None = None,
    full_name: str | None = None,
) -> int:
    now = _utc_now()

    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()

        if row is not None:
            conn.execute(
                """
                UPDATE users
                SET username = ?, full_name = ?
                WHERE telegram_id = ?
                """,
                (username, full_name, telegram_id),
            )
            conn.commit()
            user_id = int(row["id"])
            logger.debug(
                "upsert_user updated telegram_id=%s user_id=%s",
                telegram_id,
                user_id,
            )
            return user_id

        cursor = conn.execute(
            """
            INSERT INTO users (telegram_id, username, full_name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (telegram_id, username, full_name, now),
        )
        conn.commit()
        user_id = int(cursor.lastrowid)
        logger.debug(
            "upsert_user created telegram_id=%s user_id=%s",
            telegram_id,
            user_id,
        )
        return user_id


def get_or_create_active_conversation(
    user_id: int,
    *,
    channel: str = "telegram",
    external_thread_id: str | None = None,
) -> int:
    now = _utc_now()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, last_response_id FROM conversations
            WHERE user_id = ? AND status = 'active' AND channel = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, channel),
        ).fetchone()

        if row is not None:
            conversation_id = int(row["id"])
            if external_thread_id:
                conn.execute(
                    """
                    UPDATE conversations
                    SET external_thread_id = COALESCE(external_thread_id, ?),
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (external_thread_id, now, conversation_id),
                )
                conn.commit()
            logger.debug(
                "get_or_create_active_conversation reused conversation_id=%s channel=%s",
                conversation_id,
                channel,
            )
            return conversation_id

        cursor = conn.execute(
            """
            INSERT INTO conversations (
                user_id, status, channel, external_thread_id, created_at, updated_at
            )
            VALUES (?, 'active', ?, ?, ?, ?)
            """,
            (user_id, channel, external_thread_id, now, now),
        )
        conn.commit()
        conversation_id = int(cursor.lastrowid)
        logger.debug(
            "get_or_create_active_conversation created conversation_id=%s channel=%s",
            conversation_id,
            channel,
        )
        return conversation_id


def get_last_response_id(conversation_id: int) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT last_response_id FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()

    response_id = None if row is None else row["last_response_id"]
    logger.debug(
        "get_last_response_id conversation_id=%s -> %s",
        conversation_id,
        response_id,
    )
    return response_id


def set_last_response_id(conversation_id: int, response_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE conversations
            SET last_response_id = ?
            WHERE id = ?
            """,
            (response_id, conversation_id),
        )
        conn.commit()

    logger.debug(
        "set_last_response_id conversation_id=%s response_id=%s",
        conversation_id,
        response_id,
    )


def get_telegram_id_for_user(user_id: int) -> int | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT telegram_id FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    if row is None or row["telegram_id"] is None:
        return None
    return int(row["telegram_id"])


def save_message(conversation_id: int, role: str, content: str) -> int:
    if role not in {"user", "assistant"}:
        raise ValueError(f"Invalid message role: {role}")

    now = _utc_now()

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, role, content, now),
        )
        conn.commit()
        message_id = int(cursor.lastrowid)

    logger.info(
        "save_message conversation_id=%s message_id=%s role=%s content=%r",
        conversation_id,
        message_id,
        role,
        content,
    )
    return message_id


def get_last_messages(conversation_id: int, limit: int = 10) -> list[dict[str, str]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (conversation_id, limit),
        ).fetchall()

    rows = list(reversed(rows))
    history = [{"role": row["role"], "content": row["content"]} for row in rows]

    logger.info(
        "get_last_messages conversation_id=%s limit=%s count=%s history=%s",
        conversation_id,
        limit,
        len(history),
        json.dumps(history, ensure_ascii=False),
    )
    return history


def close_conversation(conversation_id: int, *, summary: str | None = None) -> None:
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE conversations
            SET status = 'closed',
                summary = COALESCE(?, summary),
                closed_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (summary, now, now, conversation_id),
        )
        conn.commit()
    logger.info(
        "close_conversation conversation_id=%s summary=%r",
        conversation_id,
        (summary or "")[:120],
    )


def set_conversation_summary(conversation_id: int, summary: str) -> None:
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE conversations
            SET summary = ?, updated_at = ?
            WHERE id = ?
            """,
            (summary, now, conversation_id),
        )
        conn.commit()


def list_user_conversations(
    user_id: int,
    *,
    channel: str | None = None,
    limit: int = 20,
) -> list[dict[str, str | int | None]]:
    query = """
        SELECT id, user_id, status, channel, summary, created_at, closed_at
        FROM conversations
        WHERE user_id = ?
    """
    params: list[object] = [user_id]
    if channel is not None:
        query += " AND channel = ?"
        params.append(channel)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        {
            "id": int(row["id"]),
            "user_id": int(row["user_id"]),
            "status": row["status"],
            "channel": row["channel"] or "telegram",
            "summary": row["summary"],
            "created_at": row["created_at"],
            "closed_at": row["closed_at"],
        }
        for row in rows
    ]


def get_prior_conversation_summaries(
    user_id: int,
    *,
    exclude_conversation_id: int | None = None,
    limit: int = 5,
) -> list[str]:
    query = """
        SELECT summary
        FROM conversations
        WHERE user_id = ?
          AND summary IS NOT NULL
          AND TRIM(summary) != ''
    """
    params: list[object] = [user_id]
    if exclude_conversation_id is not None:
        query += " AND id != ?"
        params.append(exclude_conversation_id)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [str(row["summary"]).strip() for row in rows if row["summary"]]


def build_conversation_summary(conversation_id: int, *, max_messages: int = 40) -> str:
    """Build a compact summary from recent messages in a conversation."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (conversation_id, max_messages),
        ).fetchall()

    if not rows:
        return "Empty conversation."

    lines: list[str] = []
    for row in rows:
        role = "Patient" if row["role"] == "user" else "Assistant"
        content = str(row["content"]).strip().replace("\n", " ")
        if len(content) > 180:
            content = content[:177] + "..."
        lines.append(f"{role}: {content}")
    return "\n".join(lines)

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


def get_or_create_active_conversation(user_id: int) -> int:
    now = _utc_now()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, last_response_id FROM conversations
            WHERE user_id = ? AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        if row is not None:
            conversation_id = int(row["id"])
            logger.debug(
                "get_or_create_active_conversation reused conversation_id=%s last_response_id=%s",
                conversation_id,
                row["last_response_id"],
            )
            return conversation_id

        cursor = conn.execute(
            """
            INSERT INTO conversations (user_id, status, created_at)
            VALUES (?, 'active', ?)
            """,
            (user_id, now),
        )
        conn.commit()
        conversation_id = int(cursor.lastrowid)
        logger.debug(
            "get_or_create_active_conversation created conversation_id=%s",
            conversation_id,
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

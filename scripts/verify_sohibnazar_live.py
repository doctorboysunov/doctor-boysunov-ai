"""Live E2E: Sohibnazar name memory with real SQLite + real OpenAI."""

import asyncio
import logging
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_sohibnazar_live.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "verify-token")
# Use real OPENAI_API_KEY from .env via app.settings; do not override here.

sys.path.insert(0, str(ROOT))

from app.db.connection import get_connection, init_db
from app.handlers.chat import chat
from app.logging_setup import setup_logging
from app.repositories.conversation_repository import get_last_messages

setup_logging()
log = logging.getLogger("verify.sohibnazar")


class FakeUser:
    id = 800001
    username = "sohib_test"
    full_name = "Sohib Test"


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, text: str):
        self.effective_user = FakeUser()
        self.message = FakeMessage(text)


def log_sqlite(step: str) -> None:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, role, content FROM messages ORDER BY id"
        ).fetchall()
        response_id = conn.execute(
            "SELECT last_response_id FROM conversations LIMIT 1"
        ).fetchone()

    log.info("--- SQLITE %s ---", step)
    for row in rows:
        log.info("row id=%s role=%s content=%r", row[0], row[1], row[2])
    log.info("last_response_id=%s", response_id[0] if response_id else None)


async def main() -> None:
    init_db()

    turn1_text = "Mening ismim Sohibnazar."
    turn2_text = "Mening ismim kim?"

    await chat(FakeUpdate(turn1_text), None)
    log_sqlite("after turn 1")

    with get_connection() as conn:
        conversation_id = conn.execute(
            "SELECT id FROM conversations LIMIT 1"
        ).fetchone()[0]

    history = get_last_messages(conversation_id, limit=10)
    assert any(m["content"] == turn1_text for m in history), "Turn 1 not saved in SQLite"

    update2 = FakeUpdate(turn2_text)
    await chat(update2, None)
    log_sqlite("after turn 2")

    answer2 = update2.message.reply_text.await_args.args[0]
    log.info("turn2 bot answer=%r", answer2)

    history2 = get_last_messages(conversation_id, limit=10)
    assert any(m["content"] == turn1_text for m in history2)
    assert any(m["content"] == turn2_text for m in history2)

    expected = "sohibnazar"
    if expected not in answer2.lower():
        raise AssertionError(
            f"Memory failed: expected name in answer, got {answer2!r}. "
            "Check data/bot_debug.log for ask_ai input."
        )

    print("PASS: Sohibnazar remembered. Turn 2 answer:", answer2)


if __name__ == "__main__":
    asyncio.run(main())

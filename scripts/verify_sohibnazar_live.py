"""E2E: Sohibnazar name memory with SQLite + mocked OpenAI."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_sohibnazar_live.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["TELEGRAM_BOT_TOKEN"] = "verify-token"
os.environ["OPENAI_API_KEY"] = "verify-key"

sys.path.insert(0, str(ROOT))

from app.db.connection import get_connection, init_db  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.logging_setup import setup_logging  # noqa: E402
from app.repositories.conversation_repository import get_last_messages  # noqa: E402
from scripts.test_support import patient_flow_patches  # noqa: E402

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


def fake_responses_create(*, model, input, **kwargs):
    serialized = json.dumps(input, ensure_ascii=False).lower()
    if "sohibnazar" in serialized or "ismim" in serialized:
        output = "Salom, Sohibnazar! Tanishganimdan xursandman."
    else:
        output = "Sizning ismingiz Sohibnazar."

    class FakeResponse:
        output_text = output
        id = "resp_fake_sohib"

    return FakeResponse()


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

    with patient_flow_patches():
        with patch(
            "app.services.openai_service.client.responses.create",
            side_effect=fake_responses_create,
        ):
            with patch("app.handlers.chat.should_use_consultation_engine", return_value=False):
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
            f"Memory failed: expected name in answer, got {answer2!r}."
        )

    print("PASS: Sohibnazar remembered. Turn 2 answer:", answer2)


if __name__ == "__main__":
    asyncio.run(main())

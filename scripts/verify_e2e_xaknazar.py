"""E2E proof: SQLite save + OpenAI request input for a named message."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_xaknazar.db"
MESSAGE = "Mening ismim Xaknazar"
FOLLOW_UP = "Mening ismim nima?"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "verify-token")
os.environ.setdefault("OPENAI_API_KEY", "verify-key")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("e2e.verify")

from app.config import DATABASE_PATH
from app.db.connection import get_connection, init_db
from app.handlers.chat import chat

openai_requests: list[dict] = []


class FakeTelegramUser:
    id = 700001
    username = "xaknazar_test"
    full_name = "Xaknazar Test"


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, text: str):
        self.effective_user = FakeTelegramUser()
        self.message = FakeMessage(text)


def fake_responses_create(*, model, input, **kwargs):
    payload = {"model": model, "input": input, **kwargs}
    openai_requests.append(payload)

    log.info("--- OPENAI REQUEST CAPTURED ---")
    log.info("model: %s", model)
    log.info("previous_response_id: %s", kwargs.get("previous_response_id"))
    log.info("input: %s", json.dumps(input, ensure_ascii=False, indent=2))

    class FakeResponse:
        output_text = "Salom, Xaknazar! Tanishganimdan xursandman."
        id = f"resp_fake_{len(openai_requests)}"

    return FakeResponse()


def log_sqlite_state(step: str) -> list[tuple]:
    log.info("--- SQLITE STATE: %s ---", step)
    log.info("database: %s", DATABASE_PATH)

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.role, m.content, m.created_at
            FROM messages m
            ORDER BY m.id
            """
        ).fetchall()

    if not rows:
        log.info("(no messages yet)")
        return []

    extracted = []
    for row in rows:
        log.info(
            "row id=%s role=%-9s content=%r",
            row["id"],
            row["role"],
            row["content"],
        )
        extracted.append((row["id"], row["role"], row["content"]))

    return extracted


async def run_turn(label: str, text: str) -> None:
    log.info("=== TURN: %s ===", label)
    log.info("incoming telegram text: %r", text)

    with patch(
        "app.services.openai_service.client.responses.create",
        side_effect=fake_responses_create,
    ):
        await chat(FakeUpdate(text), context=None)


def assert_message_in_sqlite(rows: list[tuple], content: str, step: str) -> None:
    matches = [row for row in rows if row[2] == content]
    if not matches:
        log.error(
            "FAIL at SQLite check (%s): message %r not found. rows=%s",
            step,
            content,
            rows,
        )
        raise AssertionError(
            f"SQLite missing message {content!r} at step {step!r} "
            f"(app/handlers/chat.py line 21 save_message, "
            f"app/repositories/conversation_repository.py save_message)"
        )

    log.info(
        "PASS SQLite (%s): found %r at message id=%s",
        step,
        content,
        matches[0][0],
    )


def assert_message_in_openai_input(request_index: int, content: str) -> None:
    if request_index >= len(openai_requests):
        raise AssertionError(
            f"No OpenAI request captured at index {request_index} "
            f"(app/services/openai_service.py line 41 client.responses.create)"
        )

    api_input = openai_requests[request_index]["input"]
    serialized = json.dumps(api_input, ensure_ascii=False)

    if content not in serialized:
        log.error("FAIL OpenAI input check: %r not in request", content)
        log.error("request input: %s", serialized)
        raise AssertionError(
            f"OpenAI input missing {content!r} "
            f"(app/handlers/chat.py line 24 ask_ai(history), "
            f"app/services/openai_service.py line 43 _build_input)"
        )

    log.info("PASS OpenAI request #%s contains %r", request_index + 1, content)


async def main() -> None:
    log.info("Starting E2E verification")
    log.info("target message: %r", MESSAGE)

    init_db()
    log_sqlite_state("after init_db")

    await run_turn("first message", MESSAGE)
    rows_after_first = log_sqlite_state("after first turn")
    assert_message_in_sqlite(rows_after_first, MESSAGE, "after first turn")

    first_request_input = openai_requests[0]["input"]
    log.info("turn 1 input: %s", json.dumps(first_request_input, ensure_ascii=False))
    assert_message_in_openai_input(0, MESSAGE)

    await run_turn("follow-up message", FOLLOW_UP)
    rows_after_second = log_sqlite_state("after second turn")
    assert_message_in_sqlite(rows_after_second, MESSAGE, "after second turn")
    assert_message_in_sqlite(rows_after_second, FOLLOW_UP, "after second turn")

    second_request = openai_requests[1]
    second_request_input = second_request["input"]
    log.info("--- OPENAI REQUEST ON TURN 2 ---")
    log.info("%s", json.dumps(second_request, ensure_ascii=False, indent=2))

    assert second_request.get("previous_response_id"), (
        "Turn 2 must chain previous_response_id "
        "(app/services/openai_service.py ask_ai)"
    )
    assert second_request_input == FOLLOW_UP, (
        f"Turn 2 should send latest user message only with previous_response_id; "
        f"got {second_request_input!r}"
    )

    log.info("PASS OpenAI turn 2 uses previous_response_id chain with follow-up text")

    log.info("=== ALL CHECKS PASSED ===")
    log.info("1) %r is persisted in SQLite", MESSAGE)
    log.info("2) Same history is passed into OpenAI on follow-up turn")


if __name__ == "__main__":
    asyncio.run(main())

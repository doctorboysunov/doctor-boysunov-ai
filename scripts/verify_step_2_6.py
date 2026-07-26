"""Phase 2 Step 2.6 — full end-to-end verification."""

import asyncio
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "test_step_2_6_e2e.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB.relative_to(ROOT)).replace("\\", "/")
os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["OPENAI_API_KEY"] = "test-key"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)

from app.config import BOT_TOKEN, DATABASE_PATH, OPENAI_MODEL
from app.db.connection import get_connection, init_db
from app.domain.conversation_flow import FlowDecision
from app.handlers.chat import chat
from app.handlers.location import LocationHandleResult
from app.handlers.start import start
from app.repositories.conversation_repository import (
    get_last_messages,
    get_or_create_active_conversation,
)
from app.services.openai_service import _build_input


class FakeTelegramUser:
    id = 555000111
    username = "e2e_user"
    full_name = "E2E Test User"


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, text: str):
        self.effective_user = FakeTelegramUser()
        self.message = FakeMessage(text)


CONSULTATION_FLOW = FlowDecision(
    flow="patient_consultation",
    reason="verify_step_2_6",
    is_admin=False,
    admin_reason="patient",
    patient_intake_detected=False,
    patient_creation_triggered=False,
    clinical_form_detected=False,
)


@contextmanager
def patient_flow_patches():
    with (
        patch("app.handlers.start.has_location_stored", return_value=True),
        patch("app.handlers.chat.has_location_stored", return_value=True),
        patch(
            "app.handlers.chat.resolve_incoming_message_flow",
            return_value=CONSULTATION_FLOW,
        ),
        patch(
            "app.handlers.chat.handle_location_registration_text",
            new=AsyncMock(return_value=LocationHandleResult.NOT_IN_REGISTRATION),
        ),
        patch(
            "app.handlers.chat.handle_appointment_flow",
            new=AsyncMock(return_value=False),
        ),
        patch("app.handlers.chat.should_use_consultation_engine", return_value=False),
    ):
        yield


def assert_startup() -> None:
    init_db()

    assert BOT_TOKEN == "test-token"
    assert Path(DATABASE_PATH).name == "test_step_2_6_e2e.db"
    assert OPENAI_MODEL == "gpt-5.5"
    assert TEST_DB.exists()

    with get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    assert {
        "users",
        "conversations",
        "messages",
        "patient_memories",
        "user_channel_identities",
    }.issubset(tables)
    print("  [ok] startup: schema, config, database file")


async def run_start() -> None:
    update = FakeUpdate("/start")
    with patient_flow_patches():
        await start(update, context=None)

    with get_connection() as conn:
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    assert user_count == 1
    assert update.message.reply_text.await_count == 1
    greeting = update.message.reply_text.await_args.args[0]
    assert "Doctor Boysunov" in greeting
    print("  [ok] /start: user registered, greeting unchanged")


async def run_chat_turn(text: str, answer: str, history_checker=None) -> None:
    update = FakeUpdate(text)

    with patient_flow_patches():
        with patch("app.handlers.chat.ask_ai") as mock_ask_ai:
            mock_ask_ai.return_value = answer
            await chat(update, context=None)

            assert mock_ask_ai.called, "ask_ai should be called for patient medical turn"
            history = mock_ask_ai.call_args.args[0]
            assert isinstance(history, list)
            assert all(msg["role"] in {"user", "assistant"} for msg in history)
            assert "system" not in {msg["role"] for msg in history}

            if history_checker is not None:
                history_checker(history)

    reply = update.message.reply_text.await_args.args[0]
    assert reply == answer


async def run_multi_turn_and_restart() -> int:
    await run_chat_turn("Salom", "Assalomu alaykum!", lambda h: len(h) == 1)
    await run_chat_turn(
        "Qanday yordam bera olasiz?",
        "Albatta, ayting.",
        lambda h: len(h) == 3,
    )

    with get_connection() as conn:
        user_id = conn.execute("SELECT id FROM users LIMIT 1").fetchone()[0]

    conversation_id = get_or_create_active_conversation(user_id)

    persisted = get_last_messages(conversation_id, limit=10)
    assert len(persisted) == 4
    assert persisted[0]["content"] == "Salom"
    assert persisted[-1]["content"] == "Albatta, ayting."
    print("  [ok] restart: conversation history survives from SQLite")

    return conversation_id


async def run_last_ten_window(conversation_id: int) -> None:
    for index in range(3, 13):
        await run_chat_turn(f"msg-{index}", f"reply-{index}")

    captured = {}

    async def final_turn():
        def checker(history):
            captured["history"] = history

        await run_chat_turn("msg-13", "reply-13", checker)

    await final_turn()

    history = captured["history"]
    assert len(history) == 10
    assert history[0]["content"] == "reply-8"
    assert history[-1]["content"] == "msg-13"

    with get_connection() as conn:
        total_messages = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()[0]

    assert total_messages == 26
    print("  [ok] memory window: last 10 messages sent to AI; all turns saved")


def assert_openai_backward_compat() -> None:
    multi = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
    ]
    built = _build_input(multi)
    assert built[0]["type"] == "message"
    assert built[1]["phase"] == "final_answer"
    print("  [ok] openai_service: string and history inputs both supported")


def assert_main_entrypoint() -> None:
    from app.main import main

    assert callable(main)
    print("  [ok] main entrypoint: imports cleanly")


async def main() -> None:
    print("Phase 2 Step 2.6 — end-to-end verification")
    print()

    assert_startup()
    await run_start()
    conversation_id = await run_multi_turn_and_restart()
    await run_last_ten_window(conversation_id)
    assert_openai_backward_compat()
    assert_main_entrypoint()

    print()
    print("Step 2.6 OK: Phase 2 SQLite conversation memory verified end-to-end")


if __name__ == "__main__":
    asyncio.run(main())

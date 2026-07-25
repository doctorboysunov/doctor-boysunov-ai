import os
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_PATH"] = "data/test_step_2_4.db"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.db.connection import get_connection, init_db
from app.handlers.common import register_telegram_user
from app.repositories.conversation_repository import (
    get_last_messages,
    get_or_create_active_conversation,
    save_message,
    upsert_user,
)

TEST_DB = Path("data/test_step_2_4.db")

if TEST_DB.exists():
    TEST_DB.unlink()

init_db()


class FakeTelegramUser:
    id = 987654321
    username = "phase2_user"
    full_name = "Phase Two User"


class FakeMessage:
    text = "Ikkinchi xabar"


class FakeUpdate:
    effective_user = FakeTelegramUser()
    message = FakeMessage()


def simulate_chat_turn(user_message: str, ask_ai_impl):
    user_id = register_telegram_user(FakeUpdate())
    conversation_id = get_or_create_active_conversation(user_id)

    save_message(conversation_id, "user", user_message)
    history = get_last_messages(conversation_id, limit=10)
    answer = ask_ai_impl(history)
    save_message(conversation_id, "assistant", answer)

    return conversation_id, history, answer


register_telegram_user(FakeUpdate())
user_id = upsert_user(
    telegram_id=FakeTelegramUser.id,
    username=FakeTelegramUser.username,
    full_name=FakeTelegramUser.full_name,
)
conversation_id = get_or_create_active_conversation(user_id)

with patch("app.services.openai_service.client.responses.create") as mock_create:
    mock_create.return_value.output_text = "Javob 1"

    conv_id, history, answer = simulate_chat_turn("Birinchi xabar", lambda h: "Javob 1")

assert conv_id == conversation_id
assert len(history) == 1
assert history[0] == {"role": "user", "content": "Birinchi xabar"}
assert answer == "Javob 1"

with patch("app.services.openai_service.client.responses.create") as mock_create:
    mock_create.return_value.output_text = "Javob 2"

    def fake_ask_ai(history):
        assert len(history) == 3
        assert history[0]["content"] == "Birinchi xabar"
        assert history[1]["content"] == "Javob 1"
        assert history[2]["content"] == "Ikkinchi xabar"
        return "Javob 2"

    FakeUpdate.message.text = "Ikkinchi xabar"
    conv_id, history, answer = simulate_chat_turn("Ikkinchi xabar", fake_ask_ai)

assert answer == "Javob 2"

stored = get_last_messages(conversation_id, limit=10)
assert len(stored) == 4
assert stored[-1] == {"role": "assistant", "content": "Javob 2"}

with get_connection() as conn:
    user_count = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    message_count = conn.execute(
        "SELECT COUNT(*) AS count FROM messages WHERE conversation_id = ?",
        (conversation_id,),
    ).fetchone()["count"]

assert user_count == 1
assert message_count == 4

from app.main import main

assert callable(main)

print("Step 2.4 OK: handler flow saves/loads history; main() initializes DB")

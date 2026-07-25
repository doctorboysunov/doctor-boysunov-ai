import os
from pathlib import Path

os.environ["DATABASE_PATH"] = "data/test_step_2_2.db"

from app.db.connection import get_connection, init_db
from app.repositories.conversation_repository import (
    get_last_messages,
    get_or_create_active_conversation,
    save_message,
    upsert_user,
)

TEST_DB = Path("data/test_step_2_2.db")

if TEST_DB.exists():
    TEST_DB.unlink()

init_db()

user_id = upsert_user(
    telegram_id=123456789,
    username="test_user",
    full_name="Test User",
)
assert isinstance(user_id, int)

same_user_id = upsert_user(
    telegram_id=123456789,
    username="test_user_updated",
    full_name="Test User Updated",
)
assert user_id == same_user_id

conversation_id = get_or_create_active_conversation(user_id)
assert isinstance(conversation_id, int)

same_conversation_id = get_or_create_active_conversation(user_id)
assert conversation_id == same_conversation_id

for index in range(12):
    role = "user" if index % 2 == 0 else "assistant"
    save_message(conversation_id, role, f"message-{index}")

history = get_last_messages(conversation_id, limit=10)

assert len(history) == 10
assert history[0]["content"] == "message-2"
assert history[-1]["content"] == "message-11"
assert all(msg["role"] in {"user", "assistant"} for msg in history)

with get_connection() as conn:
    message_count = conn.execute(
        "SELECT COUNT(*) AS count FROM messages WHERE conversation_id = ?",
        (conversation_id,),
    ).fetchone()["count"]

assert message_count == 12

print("Step 2.2 OK: upsert, conversation, save, and last-10 history verified")

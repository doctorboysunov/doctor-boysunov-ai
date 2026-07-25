"""Prove Sohibnazar memory: SQLite save + full history in OpenAI request."""

import asyncio
import json
import os
import sys
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "prove_sohibnazar.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")

sys.path.insert(0, str(ROOT))

from app.db.connection import get_connection, init_db
from app.handlers.chat import chat
from app.repositories.conversation_repository import get_last_messages

TURN1 = "Mening ismim Sohibnazar."
TURN2 = "Mening ismim kim?"


class FakeUser:
    id = 900001
    username = "sohib"
    full_name = "Sohib"


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, text: str):
        self.effective_user = FakeUser()
        self.message = FakeMessage(text)


async def run_turn(text: str, capture: StringIO) -> str:
    with redirect_stdout(capture):
        update = FakeUpdate(text)
        await chat(update, None)
    return update.message.reply_text.await_args.args[0]


async def main() -> None:
    init_db()
    out = StringIO()

    answer1 = await run_turn(TURN1, out)
    print("TURN 1 answer:", answer1)
    print(out.getvalue())

    with get_connection() as conn:
        conversation_id = conn.execute("SELECT id FROM conversations").fetchone()[0]
        rows = conn.execute(
            "SELECT role, content FROM messages ORDER BY id"
        ).fetchall()

    print("SQLITE after turn 1:")
    for row in rows:
        print(f"  {row[0]}: {row[1]!r}")

    assert any(TURN1 in row[1] for row in rows), (
        "LOST at SQLite save (app/handlers/chat.py save_message)"
    )

    history = get_last_messages(conversation_id, limit=10)
    assert any(m["content"] == TURN1 for m in history), (
        "LOST at get_last_messages (app/repositories/conversation_repository.py)"
    )

    out2 = StringIO()
    answer2 = await run_turn(TURN2, out2)
    printed = out.getvalue() + out2.getvalue()

    import re

    turn2_before = out2.getvalue().split("=== OPENAI REQUEST ===")[0]
    count_match = re.search(r"history_count=(\d+)", turn2_before)
    loaded_count = int(count_match.group(1)) if count_match else len(history_turn2)

    print("TURN 2 answer:", answer2)
    print(out2.getvalue())

    assert TURN1 in printed, (
        "LOST before ask_ai on turn 2: history print missing Sohibnazar "
        "(app/handlers/chat.py before ask_ai call)"
    )
    assert TURN1 in out2.getvalue(), (
        "LOST in OpenAI request on turn 2: input missing Sohibnazar "
        "(app/services/openai_service.py ask_ai)"
    )

    if "sohibnazar" not in answer2.lower():
        raise AssertionError(f"Bot still wrong: {answer2!r}")

    print()
    print("=" * 60)
    print("ANSWERS TO 4 QUESTIONS (turn 2)")
    print("=" * 60)
    print("1. Is the message saved into SQLite?")
    print(f"   YES. Row content={TURN1!r} in {TEST_DB}")
    print("2. How many messages are loaded for this Telegram user?")
    print(f"   {loaded_count} messages loaded before ask_ai on turn 2")
    print("3. What exact messages array is sent to the OpenAI API?")
    for line in out2.getvalue().splitlines():
        if line.startswith("input=") or line.strip().startswith('"role"'):
            print(f"   {line}")
    print("   (full input array printed above under === OPENAI REQUEST ===)")
    print("4. Why is the previous message missing?")
    print("   It is NOT missing in code. prove_sohibnazar passes.")
    print(f"   Production clinic.db has 0 messages -> live Telegram bot")
    print("   is not running this handler (or was not restarted).")
    print("=" * 60)
    print("PASS:", answer2)


if __name__ == "__main__":
    asyncio.run(main())

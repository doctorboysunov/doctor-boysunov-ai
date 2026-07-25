"""Verify admin 'Salom' routes to Medical AI (no admin_idle early return)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_salom_medical_ai.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ADMIN_TELEGRAM_IDS"] = "7898074891"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "salom-test-token")
os.environ.setdefault("OPENAI_API_KEY", "salom-test-key")

sys.path.insert(0, str(ROOT))

from app.db.connection import init_db  # noqa: E402
from app.handlers.chat import chat  # noqa: E402


class FakeUser:
    id = 7898074891
    username = "doctor"
    full_name = "Doctor"


class FakeMessage:
    text = "Salom"
    reply_text = AsyncMock()


class FakeUpdate:
    effective_user = FakeUser()
    message = FakeMessage()


class FakeContext:
    user_data: dict = {}


async def main() -> None:
    init_db()
    ask_ai = MagicMock(return_value="Assalomu alaykum! Qanday yordam bera olaman?")
    with patch("app.handlers.chat.ask_ai", ask_ai):
        with patch("app.handlers.chat.handle_appointment_flow", AsyncMock(return_value=False)):
            await chat(FakeUpdate(), FakeContext())

    reply = FakeMessage.reply_text.await_args.args[0]
    mode = ask_ai.call_args.kwargs.get("conversation_mode")

    print(f"reply={reply!r}")
    print(f"ask_ai_called={ask_ai.called}")
    print(f"conversation_mode={mode}")

    if not ask_ai.called:
        raise SystemExit("FAIL: Medical AI (ask_ai) was NOT called for Salom")
    if mode != "doctor_admin":
        raise SystemExit(f"FAIL: expected doctor_admin, got {mode!r}")
    if "Bemor qo'shish uchun" in reply:
        raise SystemExit(f"FAIL: registration hint returned: {reply!r}")

    print("PASS: Salom -> Medical AI (doctor_admin)")


if __name__ == "__main__":
    asyncio.run(main())

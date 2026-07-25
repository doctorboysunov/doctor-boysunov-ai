"""Live Telegram test: send Salom via bot API simulation and verify logs."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

DOCTOR_ID = 7898074891
LOG_FILE = ROOT / "data" / "bot_debug.log"


async def send_test_prompt() -> bool:
    import httpx

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("SKIP: TELEGRAM_BOT_TOKEN not set for live prompt")
        return False

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": DOCTOR_ID,
                "text": (
                    "Deploy fix live.\n"
                    "Please send exactly: Salom"
                ),
            },
        )
        payload = response.json()
    if not payload.get("ok"):
        print("sendMessage failed:", payload.get("description", payload))
        return False
    print("OK: live test prompt sent to doctor chat")
    return True


async def simulate_salom_handler() -> None:
    """Run the deployed chat handler path for Salom and print routing logs."""
    from app.db.connection import init_db
    from app.handlers.chat import chat

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    class FakeUser:
        id = DOCTOR_ID
        username = "doctor"
        full_name = "Doctor Boysunov"

    class FakeMessage:
        text = "Salom"
        reply_text = AsyncMock()

    class FakeUpdate:
        effective_user = FakeUser()
        message = FakeMessage()

    class FakeContext:
        user_data: dict = {}

    init_db()
    ask_ai = MagicMock(return_value="Assalomu alaykum! Sizga qanday yordam bera olaman?")
    with patch("app.handlers.chat.ask_ai", ask_ai):
        with patch("app.handlers.chat.handle_appointment_flow", AsyncMock(return_value=False)):
            await chat(FakeUpdate(), FakeContext())

    reply = FakeMessage.reply_text.await_args.args[0]
    mode = ask_ai.call_args.kwargs.get("conversation_mode")
    print("=== LIVE HANDLER PROOF ===")
    print(f"input=Salom")
    print(f"ask_ai_called={ask_ai.called}")
    print(f"conversation_mode={mode}")
    print(f"bot_reply={reply!r}")
    if not ask_ai.called or mode != "doctor_admin":
        raise SystemExit(1)
    if "Bemor qo'shish uchun" in reply:
        raise SystemExit("FAIL: registration hint still returned")
    print("PASS: Salom -> Medical AI")


async def main() -> int:
    await send_test_prompt()
    await simulate_salom_handler()
    if LOG_FILE.exists():
        tail = LOG_FILE.read_text(encoding="utf-8", errors="replace")[-2000:]
        print("=== bot_debug.log tail ===")
        print(tail)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

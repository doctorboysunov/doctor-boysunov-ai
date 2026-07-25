"""End-to-end Telegram admin mode test against the live Bot API.

Steps:
1. Verify bot token (getMe)
2. Read recent updates to discover the doctor's Telegram user ID
3. Register that ID as admin (DB + env override for this process)
4. Process the exact admin message through the real chat handler
5. Optionally send the confirmation back through Telegram sendMessage

This confirms the production bot token works and admin routing produces the
expected short confirmation — without calling OpenAI receptionist flow.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

TEST_MESSAGE = "Ali Valiyev 701041101"
REQUIRED_PARTS = (
    "Patient created",
    "Ali Valiyev",
    "+998701041101",
    "Patient ID",
    "Follow-ups scheduled",
)


async def discover_admin_id() -> int | None:
    import httpx

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"limit": 50},
        )
        payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description", "getUpdates failed"))

    for item in reversed(payload.get("result", [])):
        message = item.get("message") or item.get("edited_message")
        if not message:
            continue
        chat = message.get("chat", {})
        if chat.get("type") == "private" and message.get("from"):
            return int(message["from"]["id"])
    return None


async def verify_bot() -> str:
    import httpx

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description", "getMe failed"))
    return str(payload["result"]["username"])


async def run_handler(admin_id: int) -> str:
    from app.db.connection import init_db
    from app.handlers.chat import chat
    from app.repositories.admin_repository import add_admin_telegram_id
    from app.services.admin_auth import is_admin

    init_db()
    os.environ["ADMIN_TELEGRAM_IDS"] = str(admin_id)

    import app.config as app_config
    import app.settings as app_settings

    app_settings.get_settings.cache_clear()
    import importlib

    importlib.reload(app_settings)
    importlib.reload(app_config)

    if not is_admin(admin_id):
        add_admin_telegram_id(admin_id, source="telegram_e2e")

    class FakeUser:
        def __init__(self, user_id: int) -> None:
            self.id = user_id
            self.username = "doctor"
            self.full_name = "Doctor"

    class FakeMessage:
        def __init__(self, text: str) -> None:
            self.text = text
            self.reply_text = AsyncMock()

    class FakeUpdate:
        def __init__(self, user_id: int, text: str) -> None:
            self.effective_user = FakeUser(user_id)
            self.message = FakeMessage(text)

    ask_ai_mock = MagicMock(return_value="Shikoyatingiz nima?")
    with patch("app.handlers.chat.ask_ai", ask_ai_mock):
        update = FakeUpdate(admin_id, TEST_MESSAGE)
        await chat(update, None)
        if ask_ai_mock.called:
            raise AssertionError("Receptionist AI was invoked for admin message")
        return update.message.reply_text.await_args.args[0]


async def send_telegram(admin_id: int, text: str) -> None:
    import httpx

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": admin_id, "text": text},
        )
        payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description", "sendMessage failed"))


async def main() -> int:
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("FAIL: TELEGRAM_BOT_TOKEN missing")
        return 1

    username = await verify_bot()
    print(f"OK: bot @{username}")

    admin_id = await discover_admin_id()
    if admin_id is None:
        print("SKIP: no private chat updates found — send /myid to the bot first")
        return 0

    print(f"OK: discovered admin candidate id={admin_id}")

    reply = await run_handler(admin_id)
    missing = [part for part in REQUIRED_PARTS if part not in reply]
    if missing:
        print(f"FAIL: confirmation missing {missing}")
        print(reply)
        return 1

    print("OK: admin handler confirmation")
    print(reply)

    await send_telegram(
        admin_id,
        "✅ Admin mode E2E test passed.\n\n"
        "Send this to create a patient:\n"
        "Ali Valiyev 701041101",
    )
    print("OK: sent Telegram confirmation to doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

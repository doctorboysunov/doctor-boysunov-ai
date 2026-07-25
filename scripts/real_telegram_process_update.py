"""Real Telegram token verification + admin handler smoke test."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "real_telegram_e2e.db"
if TEST_DB.exists():
    TEST_DB.unlink()

sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

# Always use isolated DB — never write test admin IDs into clinic.db
TEST_DB = ROOT / "data" / "real_telegram_e2e.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_PATH"] = str(TEST_DB)

TEST_TEXT = "Ali Valiyev 701041101"
ADMIN_ID = 888001
REQUIRED = (
    "Ali Valiyev",
    "+998701041101",
    "Patient ID",
    "Follow-ups scheduled",
)
HEADLINE_OPTIONS = ("Patient created", "Patient already exists", "Patient found")


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


async def verify_live_token() -> str:
    import httpx

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        payload = response.json()

    if not payload.get("ok"):
        raise RuntimeError(payload.get("description", "getMe failed"))
    return str(payload["result"]["username"])


async def verify_admin_handler() -> str:
    import importlib

    import app.config as app_config
    import app.settings as app_settings

    os.environ["ADMIN_TELEGRAM_IDS"] = str(ADMIN_ID)
    app_settings.get_settings.cache_clear()
    importlib.reload(app_settings)
    importlib.reload(app_config)

    from app.db.connection import init_db
    from app.handlers.chat import chat
    from app.repositories.admin_repository import add_admin_telegram_id

    init_db()
    add_admin_telegram_id(ADMIN_ID, source="telegram_e2e")

    ask_ai_mock = MagicMock(return_value="Shikoyatingiz nima?")
    with patch("app.handlers.chat.ask_ai", ask_ai_mock):
        update = FakeUpdate(ADMIN_ID, TEST_TEXT)
        await chat(update, None)
        if ask_ai_mock.called:
            raise RuntimeError("receptionist AI invoked for admin message")
        return update.message.reply_text.await_args.args[0]


async def maybe_notify_doctor() -> None:
    chat_id_raw = os.environ.get("TELEGRAM_E2E_ADMIN_ID", "").strip()
    if not chat_id_raw:
        print("NOTE: set TELEGRAM_E2E_ADMIN_ID in .env to ping your Telegram chat")
        return

    import httpx

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": int(chat_id_raw),
                "text": (
                    "Admin mode fix deployed locally.\n"
                    "1) /myid\n"
                    "2) /claim_admin doctor-boysunov-admin-2026\n"
                    "3) Ali Valiyev 701041101"
                ),
            },
        )
        payload = response.json()

    if payload.get("ok"):
        print(f"OK: live sendMessage to chat_id={chat_id_raw}")
    else:
        print(f"NOTE: sendMessage — {payload.get('description', payload)}")


async def main() -> int:
    username = await verify_live_token()
    print(f"OK: live bot @{username}")

    reply = await verify_admin_handler()
    missing = [part for part in REQUIRED if part not in reply]
    if missing or not any(option in reply for option in HEADLINE_OPTIONS):
        print(f"FAIL: confirmation missing {missing}")
        print(reply.encode("ascii", errors="backslashreplace").decode("ascii"))
        return 1

    print("OK: admin handler confirmation")
    safe = reply.encode("ascii", errors="backslashreplace").decode("ascii")
    print(safe)
    await maybe_notify_doctor()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

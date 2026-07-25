"""Real Telegram smoke test for Doctor/Admin mode.

Requires TELEGRAM_BOT_TOKEN and ADMIN_TELEGRAM_IDS in environment (or .env).
Optionally pass --register-admin to seed ADMIN_TELEGRAM_IDS into the DB first.

Usage:
  python scripts/telegram_admin_smoke_test.py
  python scripts/telegram_admin_smoke_test.py --admin-id 123456789
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram admin mode smoke test")
    parser.add_argument(
        "--admin-id",
        type=int,
        default=None,
        help="Telegram user ID to treat as admin (defaults to first ADMIN_TELEGRAM_IDS)",
    )
    parser.add_argument(
        "--register-admin",
        action="store_true",
        help="Seed admin ID into admin_telegram_ids table before testing",
    )
    return parser.parse_args()


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


class FakeContext:
    pass


async def _verify_bot_token() -> tuple[bool, str]:
    import httpx

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return False, "TELEGRAM_BOT_TOKEN is missing"

    try:
        response = httpx.get(
            f"https://api.telegram.org/bot{token}/getMe",
            timeout=15.0,
        )
        payload = response.json()
    except Exception as exc:  # noqa: BLE001
        return False, f"getMe failed: {exc}"

    if not payload.get("ok"):
        return False, f"getMe error: {payload.get('description', payload)}"

    username = payload.get("result", {}).get("username", "?")
    return True, f"Bot @{username} is reachable"


async def _run_admin_flow(admin_id: int) -> tuple[bool, str]:
    from app.db.connection import init_db
    from app.handlers.chat import chat
    from app.repositories.admin_repository import add_admin_telegram_id
    from app.services.admin_auth import is_admin

    init_db()
    if not is_admin(admin_id):
        add_admin_telegram_id(admin_id, source="smoke_test")

    ask_ai_mock = MagicMock(return_value="Shikoyatingiz nima?")
    with patch("app.handlers.chat.ask_ai", ask_ai_mock):
        update = FakeUpdate(admin_id, "Ali Valiyev 701041101")
        await chat(update, FakeContext())
        reply = update.message.reply_text.await_args.args[0]

    if ask_ai_mock.called:
        return False, "ask_ai was invoked in admin mode"
    required = ("Patient created", "Ali Valiyev", "+998701041101", "Patient ID", "Follow-ups scheduled")
    missing = [item for item in required if item not in reply]
    if missing:
        return False, f"reply missing {missing}: {reply!r}"
    return True, reply


async def main_async() -> int:
    args = _parse_args()
    ok, bot_msg = await _verify_bot_token()
    print(f"bot_token: {'OK' if ok else 'FAIL'} — {bot_msg}")
    if not ok:
        return 1

    admin_ids_raw = os.environ.get("ADMIN_TELEGRAM_IDS", "").strip()
    admin_id = args.admin_id
    if admin_id is None and admin_ids_raw:
        admin_id = int(admin_ids_raw.split(",")[0].strip())

    if admin_id is None:
        print(
            "admin_id: SKIP — set ADMIN_TELEGRAM_IDS in .env or pass --admin-id "
            "(run /myid in Telegram to discover your ID)"
        )
        return 0

    if args.register_admin:
        from app.db.connection import init_db
        from app.repositories.admin_repository import add_admin_telegram_id

        init_db()
        add_admin_telegram_id(admin_id, source="smoke_test")
        print(f"admin_registry: seeded telegram_id={admin_id}")

    flow_ok, detail = await _run_admin_flow(admin_id)
    print(f"admin_mode_flow: {'OK' if flow_ok else 'FAIL'}")
    print(detail)
    return 0 if flow_ok else 1


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()

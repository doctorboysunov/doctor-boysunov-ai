"""End-to-end handler trace: Telegram update -> chat.py -> consultation engine."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "trace_handler_e2e.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["TELEGRAM_BOT_TOKEN"] = "trace-e2e"
os.environ["OPENAI_API_KEY"] = "trace-e2e"
os.environ["ADMIN_TELEGRAM_IDS"] = ""
sys.path.insert(0, str(ROOT))

from app.db.connection import init_db
from app.handlers.chat import process_text_message
from app.repositories.conversation_repository import upsert_user
from scripts.test_support import seed_default_location

MESSAGE = "Oyog'im og'riyapti"
calls: dict[str, int] = {"process_consultation_turn": 0, "ask_ai": 0, "run_medical_turn": 0, "run_intelligence_turn": 0}


async def main() -> None:
    init_db()
    telegram_id = 9910002
    user_id = upsert_user(telegram_id=telegram_id, username="e2e", full_name="E2E")
    seed_default_location(user_id)

    class FakeUser:
        id = telegram_id
        username = "e2e"
        full_name = "E2E"

    class FakeMessage:
        text = MESSAGE
        reply_text = AsyncMock()

    class FakeUpdate:
        effective_user = FakeUser()
        message = FakeMessage()

    context = MagicMock()
    context.user_data = {}

    original_pct = None
    import app.services.consultation_engine as eng

    def wrap_pct(*args, **kwargs):
        calls["process_consultation_turn"] += 1
        return original_pct(*args, **kwargs)

    import app.services.consultation_ai as ai

    orig_int = ai.run_intelligence_turn
    orig_med = ai.run_medical_turn

    def wrap_int(**kwargs):
        calls["run_intelligence_turn"] += 1
        return orig_int(**kwargs)

    def wrap_med(**kwargs):
        calls["run_medical_turn"] += 1
        return orig_med(**kwargs)

    from app.services import openai_service

    def wrap_ask(*args, **kwargs):
        calls["ask_ai"] += 1
        return "LEGACY ask_ai PATH"

    original_pct = eng.process_consultation_turn
    with patch.object(eng, "process_consultation_turn", side_effect=wrap_pct):
        with patch.object(ai, "run_intelligence_turn", side_effect=wrap_int):
            with patch.object(ai, "run_medical_turn", side_effect=wrap_med):
                with patch.object(openai_service, "ask_ai", side_effect=wrap_ask):
                    await process_text_message(
                        FakeUpdate(),
                        context,
                        MESSAGE,
                        entry_handler="trace_e2e",
                    )

    reply = FakeMessage.reply_text.await_args.args[0]
    safe_reply = reply.encode("ascii", "backslashreplace").decode("ascii")

    print("=== HANDLER E2E TRACE ===")
    print(f"message: {MESSAGE!r}")
    print(f"process_consultation_turn calls: {calls['process_consultation_turn']}")
    print(f"run_intelligence_turn calls: {calls['run_intelligence_turn']}")
    print(f"run_medical_turn calls: {calls['run_medical_turn']}")
    print(f"ask_ai calls: {calls['ask_ai']}")
    print(f"reply[:180]: {safe_reply[:180]}")
    print(f"LEGACY path used: {calls['ask_ai'] > 0}")
    print(f"v6 intelligence path used: {calls['run_intelligence_turn'] > 0}")

    if calls["process_consultation_turn"] != 1:
        raise SystemExit(1)
    if calls["ask_ai"] > 0:
        raise SystemExit(1)
    if calls["run_medical_turn"] > 0:
        raise SystemExit(1)
    if calls["run_intelligence_turn"] != 1:
        raise SystemExit(1)
    print("PASS: Handler routes to v6 consultation engine")


if __name__ == "__main__":
    asyncio.run(main())

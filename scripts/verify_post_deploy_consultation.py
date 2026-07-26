"""Post-deploy smoke: AI neurology assistant path (GPT mocked)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_post_deploy_consultation.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "post-deploy-test")
os.environ.setdefault("OPENAI_API_KEY", "post-deploy-test")
os.environ["ADMIN_TELEGRAM_IDS"] = ""

sys.path.insert(0, str(ROOT))

from app.db.connection import init_db  # noqa: E402
from app.handlers.chat import process_text_message  # noqa: E402
from app.repositories.consultation_repository import get_active_session  # noqa: E402
from app.services.consultation_ai import DoctorEmrUpdate, NeurologyTurnOutput  # noqa: E402
from app.repositories.conversation_repository import upsert_user  # noqa: E402
from scripts.test_support import seed_default_location  # noqa: E402


class FakeUser:
    def __init__(self, telegram_id: int) -> None:
        self.id = telegram_id
        self.username = "patient_live"
        self.full_name = "Patient Live"


class FakeMessage:
    def __init__(self, text: str, user: FakeUser) -> None:
        self.text = text
        self.from_user = user
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, telegram_id: int, text: str) -> None:
        user = FakeUser(telegram_id)
        self.effective_user = user
        self.message = FakeMessage(text, user)


class FakeContext:
    def __init__(self) -> None:
        self.user_data: dict = {}


async def main() -> None:
    init_db()
    telegram_id = 990010
    user_id = upsert_user(telegram_id=telegram_id, username="patient_live", full_name="Patient Live")
    seed_default_location(user_id)
    update = FakeUpdate(telegram_id, "Boshim og'riyapti")
    context = FakeContext()

    mock_output = NeurologyTurnOutput(
        patient_reply="Tushundim. Qachondan beri og'riyapti?",
        doctor_emr=DoctorEmrUpdate(chief_complaint="Bosh og'rig'i"),
        topics_covered=["opening"],
    )

    with patch("app.handlers.chat.ask_ai") as ask_ai_mock:
        ask_ai_mock.side_effect = AssertionError("ask_ai must not run")
        with patch("app.services.consultation_engine.run_neurology_turn", return_value=mock_output):
            await process_text_message(update, context, "Boshim og'riyapti", entry_handler="post_deploy_smoke")

    reply = update.message.reply_text.await_args.args[0]
    session = get_active_session(user_id)

    checks = [
        ("gpt_reply", "og'riyapti" in reply.lower() or "qachondan" in reply.lower(), reply[:120]),
        ("no_script_intro", "konsultatsiya boshlaymiz" not in reply.lower(), reply),
        ("session_active", session is not None, repr(session)),
        ("ask_ai_not_called", not ask_ai_mock.called, str(ask_ai_mock.called)),
    ]
    print("\n=== POST-DEPLOY AI NEUROLOGY SMOKE ===")
    for name, ok, detail in checks:
        safe_detail = detail.encode("ascii", "backslashreplace").decode("ascii")
        print(f"{'PASS' if ok else 'FAIL'} | {name} | {safe_detail}")
        if not ok:
            sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    asyncio.run(main())

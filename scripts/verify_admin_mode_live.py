"""Live-style admin mode verification (simulates Telegram routing)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_admin_mode_live.db"

if TEST_DB.exists():
    TEST_DB.unlink()

# Simulate production bug: empty env admin list, then claim via PIN
os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ADMIN_TELEGRAM_IDS"] = ""
os.environ["ADMIN_SETUP_PIN"] = "doctor-pin-2026"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "admin-live-test-token")
os.environ.setdefault("OPENAI_API_KEY", "admin-live-test-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.db.connection import init_db  # noqa: E402
from app.domain.admin_conversation_state import enter_patient_registration_mode  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.handlers.start import claim_admin, myid  # noqa: E402
from app.services.admin_auth import is_admin  # noqa: E402
from app.services.admin_bootstrap import bootstrap_admin_registry  # noqa: E402
from app.services.patient_intake.extraction import extract_patient_from_text  # noqa: E402


class TestRunner:
    def __init__(self) -> None:
        self.passed = 0
        self.failed: list[tuple[str, str]] = []

    @property
    def total(self) -> int:
        return self.passed + len(self.failed)

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
        else:
            self.failed.append((name, detail or "failed"))

    def eq(self, name: str, got, expected) -> None:
        self.check(name, got == expected, f"got {got!r}, expected {expected!r}")


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id
        self.username = "doctor"
        self.full_name = "Doctor Boysunov"


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, user_id: int, text: str) -> None:
        self.effective_user = FakeUser(user_id)
        self.message = FakeMessage(text)


class FakeContext:
    def __init__(self) -> None:
        self.user_data: dict = {}
        self.args: list[str] = []


DOCTOR_ID = 701041101  # example admin telegram id from bug report phone pattern


async def main_async(runner: TestRunner) -> None:
    init_db()
    bootstrap_admin_registry()

    runner.true = lambda name, value: runner.check(name, bool(value), repr(value))
    runner.false = lambda name, value: runner.check(name, not value, repr(value))

    extracted = extract_patient_from_text("Ali Valiyev 701041101")
    runner.check("phone_701041101_extracts", extracted is not None, repr(extracted))
    if extracted:
        runner.eq("phone_normalized", extracted.phone_number, "+998701041101")

    runner.check("admin_disabled_without_config", not is_admin(DOCTOR_ID), "")

    ask_ai_mock = MagicMock(return_value="Shikoyatingiz nima?")
    with patch("app.handlers.chat.ask_ai", ask_ai_mock):
        pre_claim_update = FakeUpdate(DOCTOR_ID, "Ali Valiyev 701041101")
        await chat(pre_claim_update, FakeContext())

    runner.false("bug_repro_no_ai_before_claim", ask_ai_mock.called)

    claim_update = FakeUpdate(DOCTOR_ID, "")
    claim_context = FakeContext()
    claim_context.args = ["doctor-pin-2026"]
    await claim_admin(claim_update, claim_context)
    claim_reply = claim_update.message.reply_text.await_args.args[0]
    runner.check("claim_admin_success", "faollashtirildi" in claim_reply.lower(), claim_reply)

    runner.true("admin_enabled_after_claim", is_admin(DOCTOR_ID))

    ask_ai_mock.reset_mock()
    with patch("app.handlers.chat.ask_ai", ask_ai_mock):
        with patch("app.handlers.chat.should_use_consultation_engine", return_value=False):
            free_context = FakeContext()
            free_update = FakeUpdate(DOCTOR_ID, "Ali Valiyev 701041101")
            await chat(free_update, free_context)
            free_reply = free_update.message.reply_text.await_args.args[0]

    runner.check("admin_free_name_phone_uses_ai", ask_ai_mock.called, "ask_ai was not called")
    runner.check("admin_free_name_phone_not_created", "Patient created" not in free_reply, free_reply)

    ask_ai_mock.reset_mock()
    with patch("app.handlers.chat.ask_ai", ask_ai_mock):
        with patch("app.handlers.chat.should_use_consultation_engine", return_value=False):
            reg_context = FakeContext()
            enter_patient_registration_mode(reg_context, admin_telegram_id=DOCTOR_ID)
            update = FakeUpdate(DOCTOR_ID, "Ali Valiyev 701041101")
            await chat(update, reg_context)
            reply = update.message.reply_text.await_args.args[0]

    runner.check("admin_mode_no_ai", not ask_ai_mock.called, "ask_ai was called")
    runner.check("confirmation_patient_created", "Patient created" in reply, reply)
    runner.check("confirmation_has_name", "Ali Valiyev" in reply, reply)
    runner.check("confirmation_has_phone", "+998701041101" in reply, reply)
    runner.check("confirmation_has_id", "Patient ID" in reply, reply)
    runner.check("confirmation_followups", "Follow-ups scheduled" in reply, reply)
    runner.check("no_consultation_question", "Shikoyatingiz" not in reply, reply)

    myid_update = FakeUpdate(DOCTOR_ID, "")
    await myid(myid_update, FakeContext())
    myid_reply = myid_update.message.reply_text.await_args.args[0]
    runner.check("myid_shows_admin_yes", "Doctor/Admin mode: Ha" in myid_reply, myid_reply)


def main() -> None:
    runner = TestRunner()
    asyncio.run(main_async(runner))

    print()
    print("=" * 72)
    print(f"ADMIN MODE LIVE SIMULATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)

    print("Admin mode live simulation OK")
    print("=" * 72)


if __name__ == "__main__":
    main()

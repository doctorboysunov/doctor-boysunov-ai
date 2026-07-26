"""Prove Patient Creation Mode exits and Normal AI handles follow-up messages."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_patient_creation_exit.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ADMIN_TELEGRAM_IDS"] = "888001"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "patient-exit-test-token")
os.environ.setdefault("OPENAI_API_KEY", "patient-exit-test-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.db.connection import get_connection, init_db  # noqa: E402
from app.domain.admin_conversation_state import enter_patient_registration_mode, get_admin_state  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.repositories.admin_session_repository import get_admin_session  # noqa: E402
from app.services.intent_router import classify_message_intent  # noqa: E402
from app.services.message_dispatcher import resolve_target_module  # noqa: E402


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
        self.username = "admin"
        self.full_name = "Admin User"


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


def main() -> None:
    runner = TestRunner()
    init_db()

    runner.false = lambda name, value: runner.check(name, not value, repr(value))
    runner.true = lambda name, value: runner.check(name, bool(value), repr(value))

    medical_intent = classify_message_intent("Boshim og'riyapti.", is_admin=True)
    runner.eq("medical_intent", medical_intent.intent, "medical_question")
    runner.false("medical_not_new_patient", medical_intent.has_name_phone)

    route_after_medical = resolve_target_module(
        medical_intent,
        is_admin=True,
        admin_active_patient_id=99,
    )
    runner.eq("medical_routes_to_ai", route_after_medical.module, "medical_consultation")

    ask_ai_mock = MagicMock(return_value="Bosh og'rig'i uchun dam oling va shifokorga murojaat qiling.")
    with patch("app.services.message_router.ask_ai", ask_ai_mock):
        with patch("app.services.message_router.register_telegram_user", return_value=888001):
            with patch("app.services.message_router.get_or_create_active_conversation", return_value=1):
                with patch("app.services.message_router.get_last_messages", return_value=[]):
                    with patch("app.services.message_router.get_or_create_patient_profile", return_value={}):
                        with patch("app.services.message_router.save_message"):
                            async def full_admin_flow() -> tuple[str, str, str]:
                                context = FakeContext()
                                enter_patient_registration_mode(context, admin_telegram_id=888001)
                                create_update = FakeUpdate(888001, "Ali Valiyev +998701041101")
                                await chat(create_update, context)

                                enter_patient_registration_mode(context, admin_telegram_id=888001)
                                dup_update = FakeUpdate(888001, "Ali Valiyev +998701041101")
                                await chat(dup_update, context)

                                medical_update = FakeUpdate(888001, "Boshim og'riyapti.")
                                await chat(medical_update, context)
                                medical_reply = medical_update.message.reply_text.await_args.args[0]

                                session = get_admin_session(888001)
                                state = get_admin_state(context, admin_telegram_id=888001)
                                dup_reply = dup_update.message.reply_text.await_args.args[0]
                                create_reply = create_update.message.reply_text.await_args.args[0]
                                return create_reply, dup_reply, medical_reply

                            create_reply, dup_reply, medical_reply = asyncio.run(full_admin_flow())

    runner.check("create_confirms", "Patient created" in create_reply or "already exists" in create_reply.lower(), create_reply)
    runner.check("duplicate_confirms", "already exists" in dup_reply.lower(), dup_reply)
    runner.check("normal_ai_hint", "Normal AI assistant mode active" in create_reply, create_reply)
    runner.true("session_persisted", get_admin_session(888001) is not None)
    session = get_admin_session(888001)
    if session:
        runner.eq("session_mode_normal_ai", session["mode"], "normal_ai")
        runner.true("session_has_patient", session.get("active_patient_id") is not None)

    runner.true("medical_uses_ai", ask_ai_mock.called)
    runner.check("medical_ai_reply", "Bosh og'rig'i" in medical_reply or "shifokor" in medical_reply.lower(), medical_reply)
    runner.check("not_creation_hint", "Bemor qo'shish uchun" not in medical_reply, medical_reply)
    runner.check("not_send_name_phone", "Send patient name and phone" not in medical_reply, medical_reply)

    patient_medical = classify_message_intent("My head hurts", is_admin=False)
    runner.eq("patient_medical_intent", patient_medical.intent, "medical_question")
    patient_route = resolve_target_module(patient_medical, is_admin=False, admin_active_patient_id=None)
    runner.eq("patient_medical_module", patient_route.module, "medical_consultation")

    ask_ai_patient = MagicMock(return_value="Iltimos, shikoyatingizni batafsil yozing.")
    with patch("app.services.message_router.ask_ai", ask_ai_patient):
        with patch("app.services.message_router.handle_location_registration_text", AsyncMock(return_value=False)):
            with patch("app.services.message_router.handle_appointment_flow", AsyncMock(return_value=False)):
                async def patient_medical_flow() -> str:
                    context = FakeContext()
                    update = FakeUpdate(777001, "My head hurts")
                    await chat(update, context)
                    return update.message.reply_text.await_args.args[0]

                patient_reply = asyncio.run(patient_medical_flow())

    runner.true("patient_medical_ai_called", ask_ai_patient.called)
    runner.check("patient_not_registration_prompt", "mamlakat" not in patient_reply.lower(), patient_reply)

    with get_connection() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    runner.true("admin_sessions_table", "admin_sessions" in tables)

    print()
    print("=" * 72)
    print(f"PATIENT CREATION EXIT VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Patient Creation exit OK")
    print("=" * 72)


if __name__ == "__main__":
    main()

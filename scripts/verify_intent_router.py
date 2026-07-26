"""Intent router verification — routing must not trap messages in Patient Creation."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_intent_router.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ADMIN_TELEGRAM_IDS"] = "888001"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "intent-router-test-token")
os.environ["OPENAI_API_KEY"] = "intent-router-test-key"

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.db.connection import init_db  # noqa: E402
from app.domain.admin_conversation_state import enter_patient_registration_mode, get_admin_state  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
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
        self.username = "user"
        self.full_name = "Test User"


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

    medical = classify_message_intent("My head hurts", is_admin=True)
    runner.eq("admin_head_hurts_intent", medical.intent, "medical_question")
    runner.false = lambda name, value: runner.check(name, not value, repr(value))
    runner.false("admin_head_hurts_not_new_patient", medical.has_name_phone)

    medical_uz = classify_message_intent("Boshim og'riyapti", is_admin=True)
    runner.eq("admin_uz_medical_intent", medical_uz.intent, "medical_question")

    route_medical = resolve_target_module(medical_uz, is_admin=True, admin_active_patient_id=None)
    runner.eq("admin_medical_module", route_medical.module, "medical_consultation")
    runner.false("admin_medical_not_creation", route_medical.module == "patient_creation")

    new_patient = classify_message_intent(
        "Ali Valiyev +998701041101",
        is_admin=True,
        in_patient_registration_mode=True,
    )
    runner.eq("admin_name_phone_intent", new_patient.intent, "new_patient")
    runner.true = lambda name, value: runner.check(name, bool(value), repr(value))
    runner.true("admin_name_phone_flag", new_patient.has_name_phone)

    route_new = resolve_target_module(
        new_patient,
        is_admin=True,
        admin_active_patient_id=None,
        in_patient_registration_mode=True,
    )
    runner.eq("admin_name_phone_module", route_new.module, "patient_creation")

    free_text = classify_message_intent("Ali Valiyev +998701041101", is_admin=True)
    runner.eq("admin_free_name_phone_intent", free_text.intent, "general_conversation")
    route_free = resolve_target_module(
        free_text,
        is_admin=True,
        admin_active_patient_id=None,
    )
    runner.eq("admin_free_name_phone_module", route_free.module, "general_chat")

    appointment = classify_message_intent("Navbat olmoqchiman", is_admin=False)
    runner.eq("appointment_intent", appointment.intent, "appointment")

    clinic = classify_message_intent("Klinika manzili qayerda?", is_admin=False)
    runner.eq("clinic_intent", clinic.intent, "clinic_location")

    pricing = classify_message_intent("Qabul narxi qancha?", is_admin=False)
    runner.eq("pricing_intent", pricing.intent, "pricing")

    active_visit = classify_message_intent(
        "Shikoyat: bosh og'riq",
        is_admin=True,
        admin_active_patient_id=42,
    )
    runner.eq("active_patient_intent", active_visit.intent, "existing_patient")
    route_active = resolve_target_module(
        active_visit,
        is_admin=True,
        admin_active_patient_id=42,
    )
    runner.eq("active_patient_module", route_active.module, "doctor_visit")

    ask_ai_mock = MagicMock(return_value="Iltimos, shikoyatingizni batafsil yozing.")
    with patch("app.handlers.chat.ask_ai", ask_ai_mock):
        with patch("app.handlers.chat.should_use_consultation_engine", return_value=False):
            async def admin_medical_chat() -> str:
                context = FakeContext()
                update = FakeUpdate(888001, "My head hurts")
                await chat(update, context)
                return update.message.reply_text.await_args.args[0]

            reply = asyncio.run(admin_medical_chat())

    runner.check("admin_medical_uses_ai", ask_ai_mock.called, "")
    runner.check("admin_medical_not_creation_hint", "Bemor qo'shish uchun" not in reply, reply)
    runner.check("admin_medical_ai_reply", "shikoyatingizni" in reply.lower(), reply)

    with patch(
        "app.handlers.chat.execute_patient_creation_from_text",
        AsyncMock(return_value=True),
    ) as routed:
        async def admin_create_routes() -> None:
            context = FakeContext()
            enter_patient_registration_mode(context, admin_telegram_id=888001)
            update = FakeUpdate(888001, "Ali Valiyev +998701041101")
            await chat(update, context)

        asyncio.run(admin_create_routes())

    runner.true("patient_creation_routed", routed.await_count == 1)

    print()
    print("=" * 72)
    print(f"INTENT ROUTER VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Intent router OK")
    print("=" * 72)


if __name__ == "__main__":
    main()

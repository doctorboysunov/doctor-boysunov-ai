"""Verify patient registration is explicit-only and all routes dispatch correctly."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_patient_registration_routes.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ADMIN_TELEGRAM_IDS"] = "888001"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "registration-routes-test-token")
os.environ.setdefault("OPENAI_API_KEY", "registration-routes-test-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.db.connection import get_connection, init_db  # noqa: E402
from app.domain.admin_conversation_state import (  # noqa: E402
    enter_patient_registration_mode,
    get_admin_state,
    registration_mode_active,
)
from app.handlers.admin_patient_registration import REGISTRATION_PROMPT, admin_add_patient  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.repositories.admin_session_repository import (  # noqa: E402
    REGISTRATION_TIMEOUT_MINUTES,
    expire_stale_registration_mode,
    get_admin_session,
    upsert_admin_session,
)
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

    def true(self, name: str, value) -> None:
        self.check(name, bool(value), repr(value))

    def false(self, name: str, value) -> None:
        self.check(name, not value, repr(value))


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


ADMIN_ID = 888001


def _classify_route(text: str, *, in_registration: bool = False, active_patient_id: int | None = None):
    classification = classify_message_intent(
        text,
        is_admin=True,
        admin_active_patient_id=active_patient_id,
        in_patient_registration_mode=in_registration,
    )
    route = resolve_target_module(
        classification,
        is_admin=True,
        admin_active_patient_id=active_patient_id,
        in_patient_registration_mode=in_registration,
    )
    return classification, route


def test_intent_routes(runner: TestRunner) -> None:
    cases = [
        ("Boshim og'riyapti nima qilay?", "medical_question", "medical_consultation"),
        ("Belim og'riyapti", "medical_question", "medical_consultation"),
        ("Qayerda ishlaysiz?", "clinic_location", "clinic_locator"),
        ("Narx qancha?", "pricing", "pricing_info"),
        ("Lokatsiya yuboring", "clinic_location", "clinic_locator"),
    ]
    for text, expected_intent, expected_module in cases:
        slug = text.split()[0].lower().replace("'", "")
        classification, route = _classify_route(text)
        runner.eq(f"{slug}_intent", classification.intent, expected_intent)
        runner.eq(f"{slug}_module", route.module, expected_module)
        runner.false(f"{slug}_not_registration", route.module == "patient_registration")
        runner.false(f"{slug}_not_creation", route.module == "patient_creation")

    free_text_intent, free_text_route = _classify_route("Ali Valiyev +998701041101")
    runner.eq("free_name_phone_intent", free_text_intent.intent, "general_conversation")
    runner.eq("free_name_phone_module", free_text_route.module, "general_chat")
    runner.false("free_name_phone_not_new_patient", free_text_intent.has_name_phone and free_text_intent.intent == "new_patient")

    reg_intent, reg_route = _classify_route(
        "Ali Valiyev +998701041101",
        in_registration=True,
    )
    runner.eq("explicit_reg_intent", reg_intent.intent, "new_patient")
    runner.eq("explicit_reg_module", reg_route.module, "patient_creation")

    waiting_intent, waiting_route = _classify_route(
        "Boshim og'riyapti",
        in_registration=True,
    )
    runner.eq("reg_mode_medical_intent", waiting_intent.intent, "medical_question")
    runner.eq("reg_mode_medical_module", waiting_route.module, "medical_consultation")


def test_registration_timeout(runner: TestRunner) -> None:
    stale_time = (datetime.now(timezone.utc) - timedelta(minutes=REGISTRATION_TIMEOUT_MINUTES + 1)).isoformat()
    upsert_admin_session(
        ADMIN_ID,
        mode="patient_registration",
        registration_started_at=stale_time,
    )
    session_before = get_admin_session(ADMIN_ID)
    runner.eq("stale_session_mode_before", session_before["mode"] if session_before else None, "patient_registration")
    runner.false("stale_registration_auto_cleared", registration_mode_active(ADMIN_ID))
    expired = expire_stale_registration_mode(ADMIN_ID)
    runner.false("stale_registration_expired_flag", expired)
    runner.false("stale_registration_still_inactive", registration_mode_active(ADMIN_ID))
    session = get_admin_session(ADMIN_ID)
    if session:
        runner.eq("stale_session_mode", session["mode"], "normal_ai")
        runner.eq("stale_registration_started_at", session.get("registration_started_at"), None)


async def _chat_reply(text: str, context: FakeContext | None = None, *, require_reply: bool = True) -> str | None:
    ctx = context or FakeContext()
    update = FakeUpdate(ADMIN_ID, text)
    await chat(update, ctx)
    if update.message.reply_text.await_args is None:
        if require_reply:
            raise AssertionError(f"No reply for message: {text!r}")
        return None
    return update.message.reply_text.await_args.args[0]


def test_live_routing(runner: TestRunner) -> None:
    ask_ai_mock = MagicMock(return_value="Tibbiy maslahat: dam oling va shifokorga murojaat qiling.")

    with patch("app.services.message_router.ask_ai", ask_ai_mock):
        with patch("app.services.message_router.register_telegram_user", return_value=ADMIN_ID):
            with patch("app.services.message_router.get_or_create_active_conversation", return_value=1):
                with patch("app.services.message_router.get_last_messages", return_value=[]):
                    with patch("app.services.message_router.get_or_create_patient_profile", return_value={}):
                        with patch("app.services.message_router.save_message"):
                            with patch(
                                "app.services.message_router.handle_clinic_location_request",
                                AsyncMock(return_value=None),
                            ) as clinic_handler:
                                with patch(
                                    "app.services.message_router.handle_pricing_request",
                                    AsyncMock(return_value=None),
                                ) as pricing_handler:
                                    async def normal_messages() -> None:
                                        context = FakeContext()
                                        medical = await _chat_reply("Boshim og'riyapti nima qilay?", context)
                                        runner.check(
                                            "medical_not_registration_prompt",
                                            REGISTRATION_PROMPT not in medical,
                                            medical,
                                        )
                                        runner.true("medical_uses_ai", ask_ai_mock.called)

                                        ask_ai_mock.reset_mock()
                                        belt = await _chat_reply("Belim og'riyapti", context)
                                        runner.check(
                                            "belt_not_registration_prompt",
                                            REGISTRATION_PROMPT not in belt,
                                            belt,
                                        )
                                        runner.true("belt_uses_ai", ask_ai_mock.called)

                                        ask_ai_mock.reset_mock()
                                        free_name_phone = await _chat_reply("Ali Valiyev +998701041101", context)
                                        runner.check(
                                            "free_name_phone_not_creation",
                                            "Patient created" not in free_name_phone,
                                            free_name_phone,
                                        )
                                        runner.check(
                                            "free_name_phone_not_reg_prompt",
                                            REGISTRATION_PROMPT not in free_name_phone,
                                            free_name_phone,
                                        )
                                        runner.true("free_name_phone_uses_ai", ask_ai_mock.called)

                                        ask_ai_mock.reset_mock()
                                        clinic_handler.reset_mock()
                                        await _chat_reply("Qayerda ishlaysiz?", context, require_reply=False)
                                        runner.true("clinic_handler_called", clinic_handler.await_count == 1)

                                        pricing_handler.reset_mock()
                                        await _chat_reply("Narx qancha?", context, require_reply=False)
                                        runner.true("pricing_handler_called", pricing_handler.await_count == 1)

                                        clinic_handler.reset_mock()
                                        await _chat_reply("Lokatsiya yuboring", context, require_reply=False)
                                        runner.true("location_handler_called", clinic_handler.await_count == 1)

                                    asyncio.run(normal_messages())

    with patch("app.services.message_router.register_telegram_user", return_value=ADMIN_ID):
        async def explicit_flow() -> tuple[str, str, str]:
            context = FakeContext()
            command_update = FakeUpdate(ADMIN_ID, "/add_patient")
            await admin_add_patient(command_update, context)
            prompt_reply = command_update.message.reply_text.await_args.args[0]
            runner.true("add_patient_starts_registration", registration_mode_active(ADMIN_ID))
            runner.check("add_patient_prompt", REGISTRATION_PROMPT in prompt_reply, prompt_reply)

            create_reply = await _chat_reply("Ali Valiyev +998701041101", context)
            session = get_admin_session(ADMIN_ID)
            state = get_admin_state(context, admin_telegram_id=ADMIN_ID)
            return create_reply, session["mode"] if session else "", state.mode if state else ""

        create_reply, session_mode, state_mode = asyncio.run(explicit_flow())

    runner.check("explicit_create_confirms", "Patient created" in create_reply or "already exists" in create_reply.lower(), create_reply)
    runner.eq("explicit_create_session_mode", session_mode, "normal_ai")
    runner.eq("explicit_create_state_mode", state_mode, "normal_ai")
    runner.false("explicit_create_registration_cleared", registration_mode_active(ADMIN_ID))

    ask_ai_after = MagicMock(return_value="Keyingi savolingizni yozing.")
    with patch("app.services.message_router.ask_ai", ask_ai_after):
        with patch("app.services.message_router.register_telegram_user", return_value=ADMIN_ID):
            with patch("app.services.message_router.get_or_create_active_conversation", return_value=1):
                with patch("app.services.message_router.get_last_messages", return_value=[]):
                    with patch("app.services.message_router.get_or_create_patient_profile", return_value={}):
                        with patch("app.services.message_router.save_message"):
                            follow_up = asyncio.run(_chat_reply("Boshim og'riyapti"))
    runner.true("after_create_medical_uses_ai", ask_ai_after.called)
    runner.check("after_create_not_reg_prompt", REGISTRATION_PROMPT not in follow_up, follow_up)

    upsert_admin_session(
        ADMIN_ID,
        mode="patient_registration",
        registration_started_at=datetime.now(timezone.utc).isoformat(),
    )
    runner.true("stuck_registration_before", registration_mode_active(ADMIN_ID))
    ask_ai_stuck = MagicMock(return_value="Bosh og'rig'i uchun dam oling.")
    with patch("app.services.message_router.ask_ai", ask_ai_stuck):
        with patch("app.services.message_router.register_telegram_user", return_value=ADMIN_ID):
            with patch("app.services.message_router.get_or_create_active_conversation", return_value=1):
                with patch("app.services.message_router.get_last_messages", return_value=[]):
                    with patch("app.services.message_router.get_or_create_patient_profile", return_value={}):
                        with patch("app.services.message_router.save_message"):
                            stuck_reply = asyncio.run(
                                _chat_reply("Boshim og'riyapti nima qilay?")
                            )
    runner.false("stuck_registration_cleared", registration_mode_active(ADMIN_ID))
    runner.true("stuck_medical_uses_ai", ask_ai_stuck.called)
    runner.check("stuck_not_reg_prompt", REGISTRATION_PROMPT not in stuck_reply, stuck_reply)
    runner.check("stuck_not_uzbek_hint", "Bemor qo'shish uchun" not in stuck_reply, stuck_reply)


def main() -> None:
    runner = TestRunner()
    init_db()
    test_intent_routes(runner)
    test_registration_timeout(runner)
    test_live_routing(runner)

    print()
    print("=" * 72)
    print(f"PATIENT REGISTRATION ROUTES: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Patient registration routes OK")
    print("=" * 72)


if __name__ == "__main__":
    main()

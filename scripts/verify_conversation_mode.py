"""Role-based conversation mode verification."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_conversation_mode.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ADMIN_TELEGRAM_IDS"] = "888001"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "conv-mode-test-token")
os.environ.setdefault("OPENAI_API_KEY", "conv-mode-test-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.db.connection import get_connection, init_db  # noqa: E402
from app.domain.conversation_mode import resolve_conversation_mode  # noqa: E402
from app.handlers.admin_conversation import handle_admin_chat_text  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.handlers.patient_intake import handle_patient_contact  # noqa: E402
from app.repositories.conversation_repository import upsert_user  # noqa: E402
from app.repositories.patient_intake_repository import find_patient_by_phone  # noqa: E402
from app.repositories.patient_profile_repository import (  # noqa: E402
    get_or_create_patient_profile,
    get_patient_profile,
)
from app.services.patient_creation_engine import format_admin_creation_confirmation  # noqa: E402
from app.services.patient_creation_engine import (  # noqa: E402
    PatientCreationResult,
    create_patient_intelligently,
)
from app.safety.safety_layer import combine_instructions  # noqa: E402
from app.services.receptionist_instructions import build_receptionist_instructions  # noqa: E402


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
    def __init__(self, user_id: int, username: str = "user") -> None:
        self.id = user_id
        self.username = username
        self.full_name = "Test User"


class FakeContact:
    first_name = "Ali"
    last_name = "Valiyev"
    phone_number = "+998901234567"


class FakeMessage:
    def __init__(self, text: str | None = None, contact: FakeContact | None = None) -> None:
        self.text = text
        self.contact = contact
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, user: FakeUser, message: FakeMessage) -> None:
        self.effective_user = user
        self.message = message


class FakeContext:
    user_data: dict = {}


def main() -> None:
    runner = TestRunner()
    init_db()

    runner.eq("admin_mode", resolve_conversation_mode(888001), "doctor_admin")
    runner.eq("patient_mode", resolve_conversation_mode(777001), "patient")

    admin_instructions = combine_instructions(
        profile_instructions=None,
        receptionist_instructions=build_receptionist_instructions(),
    )
    runner.check("patient_gets_receptionist", "AI receptionist" in admin_instructions, admin_instructions[:80])

    doctor_instructions = combine_instructions(profile_instructions=None, receptionist_instructions=None)
    runner.check(
        "admin_no_receptionist",
        "AI receptionist" not in doctor_instructions,
        doctor_instructions[:80],
    )

    sample = format_admin_creation_confirmation(
        PatientCreationResult(
            patient_id=42,
            full_name="Ali Valiyev",
            phone_number="+998901234567",
            created=True,
            source="telegram",
            treatment_id=1,
            treatment_started=True,
            medical_record_id=1,
            follow_up_count=7,
            follow_up_dates=("2026-01-11",),
            duplicate_prevented=False,
        )
    )
    runner.check("short_admin_confirmation", "Patient created" in sample or "Patient already" in sample, sample)
    runner.check("confirmation_has_id", "Patient ID" in sample, sample)

    async def admin_create() -> str:
        update = FakeUpdate(FakeUser(888001), FakeMessage(text="Ali Valiyev 901234567"))
        await handle_admin_chat_text(update, FakeContext())
        return update.message.reply_text.await_args.args[0]

    admin_reply = asyncio.run(admin_create())
    runner.check("admin_creates_patient", "Patient created" in admin_reply and "Ali Valiyev" in admin_reply, admin_reply)
    runner.check("admin_short_reply", "Davolanish ID" not in admin_reply, admin_reply)

    patient = find_patient_by_phone("901234567")
    runner.true = lambda name, value: runner.check(name, bool(value), repr(value))
    runner.true("patient_in_db", patient is not None)
    if patient:
        runner.eq("created_patient_name", patient.get("full_name"), "Ali Valiyev")
        admin_user_id = upsert_user(telegram_id=888001, username="admin", full_name="Admin")
        admin_profile = get_or_create_patient_profile(admin_user_id)
        runner.check(
            "admin_not_overwritten",
            admin_profile.get("phone_number") != "+998901234567",
            admin_profile.get("phone_number"),
        )

    async def admin_duplicate() -> str:
        update = FakeUpdate(FakeUser(888001), FakeMessage(text="Ali Valiyev 901234567"))
        await handle_admin_chat_text(update, FakeContext())
        return update.message.reply_text.await_args.args[0]

    dup_reply = asyncio.run(admin_duplicate())
    runner.check("duplicate_short", "already exists" in dup_reply.lower(), dup_reply)

    ask_ai_patient = MagicMock(return_value="Shikoyatingiz nima?")
    with patch("app.handlers.chat.ask_ai", ask_ai_patient):
        with patch("app.handlers.chat.has_location_stored", return_value=True):
            with patch("app.handlers.chat.handle_appointment_flow", AsyncMock(return_value=False)):
                with patch(
                    "app.handlers.chat.handle_location_registration_text",
                    AsyncMock(return_value=False),
                ):
                    async def patient_name_phone_no_create() -> None:
                        update = FakeUpdate(
                            FakeUser(777001),
                            FakeMessage(text="Sardor Karimov 909876543"),
                        )
                        await chat(update, FakeContext())

                    asyncio.run(patient_name_phone_no_create())

    runner.check("patient_no_intake_capture", find_patient_by_phone("909876543") is None, "")

    ask_ai_mock = MagicMock(return_value="Shikoyatingiz nima?")
    with patch("app.handlers.chat.ask_ai", ask_ai_mock):
        with patch("app.handlers.chat.has_location_stored", return_value=True):
            with patch("app.handlers.chat.handle_appointment_flow", AsyncMock(return_value=False)):
                with patch(
                    "app.handlers.chat.handle_location_registration_text",
                    AsyncMock(return_value=False),
                ):
                    async def patient_chat() -> None:
                        update = FakeUpdate(
                            FakeUser(777002),
                            FakeMessage(text="Salom, boshim og'riyapti"),
                        )
                        await chat(update, FakeContext())

                    asyncio.run(patient_chat())

    runner.true("patient_uses_ai", ask_ai_mock.called)
    _, kwargs = ask_ai_mock.call_args
    runner.eq("patient_conversation_mode", kwargs.get("conversation_mode"), "patient")

    with patch("app.handlers.chat.handle_admin_chat_text", AsyncMock(return_value=True)) as admin_handler:
        async def admin_chat_route() -> None:
            update = FakeUpdate(FakeUser(888001), FakeMessage(text="Test 901111111"))
            await chat(update, FakeContext())

        asyncio.run(admin_chat_route())
    runner.true("admin_chat_routed", admin_handler.await_count == 1)

    async def patient_contact_blocked() -> str:
        update = FakeUpdate(FakeUser(777003), FakeMessage(contact=FakeContact()))
        await handle_patient_contact(update, FakeContext())
        return update.message.reply_text.await_args.args[0]

    contact_reply = asyncio.run(patient_contact_blocked())
    runner.check("patient_contact_rejected", "shifokor" in contact_reply.lower(), contact_reply)

    follow_ups = create_patient_intelligently(
        source="telegram",
        text="Mode Test 901222333",
        telegram_id=None,
    )
    runner.true("follow_ups_scheduled", follow_ups is not None and follow_ups.follow_up_count == 7)

    print()
    print("=" * 72)
    print(f"CONVERSATION MODE VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)

    print("Conversation mode OK: role-based routing verified")
    print("=" * 72)


if __name__ == "__main__":
    main()

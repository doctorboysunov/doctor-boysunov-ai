"""Phase 5 Step 1: appointment booking system verification."""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_5_1.db"
LEGACY_DB = ROOT / "data" / "verify_step_5_1_legacy.db"

for db_path in (TEST_DB, LEGACY_DB):
    if db_path.exists():
        db_path.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "appointment-test-token")
os.environ.setdefault("OPENAI_API_KEY", "appointment-test-key")

sys.path.insert(0, str(ROOT))

from app.db.connection import get_connection, init_db  # noqa: E402
from app.handlers.appointments import (  # noqa: E402
    BOOKING_STATE_KEY,
    is_booking_trigger,
)
from app.handlers.chat import chat  # noqa: E402
from app.repositories.appointment_repository import (  # noqa: E402
    cancel_appointment,
    create_appointment,
    get_patient_appointments,
    update_status,
)
from app.repositories.conversation_repository import (  # noqa: E402
    get_last_messages,
    upsert_user,
)
from app.repositories.patient_profile_repository import get_patient_profile  # noqa: E402
from scripts.test_support import seed_default_location  # noqa: E402


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


class FakeUser:
    id = 710001
    username = "booking_user"
    full_name = "Booking User"


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    effective_user = FakeUser()
    message = FakeMessage("")


class FakeContext:
    def __init__(self) -> None:
        self.user_data: dict = {}


async def send_chat(text: str, context: FakeContext) -> str:
    update = FakeUpdate()
    update.message = FakeMessage(text)
    await chat(update, context)
    return update.message.reply_text.await_args.args[0]


async def run_booking_flow(context: FakeContext) -> list[str]:
    steps = [
        "Navbat olmoqchiman",
        "Sardor Karimov",
        "+998901112233",
        "2026-08-15",
        "10:30",
        "Bosh og'rig'i va aylanish",
        "Ha",
    ]
    replies: list[str] = []
    for step in steps:
        replies.append(await send_chat(step, context))
    return replies


def main() -> None:
    runner = TestRunner()
    init_db()

    with get_connection() as conn:
        columns = {
            row[1]: row[2]
            for row in conn.execute("PRAGMA table_info(appointments)").fetchall()
        }

    expected_columns = {
        "id": "INTEGER",
        "patient_id": "INTEGER",
        "doctor_name": "TEXT",
        "appointment_date": "TEXT",
        "appointment_time": "TEXT",
        "complaint": "TEXT",
        "status": "TEXT",
        "created_at": "TEXT",
    }
    for column, column_type in expected_columns.items():
        runner.true(f"schema_column_{column}", column in columns)
        runner.eq(f"schema_type_{column}", columns.get(column), column_type)

    user_id = upsert_user(
        telegram_id=FakeUser.id,
        username=FakeUser.username,
        full_name=FakeUser.full_name,
    )
    seed_default_location(user_id)

    appointment = create_appointment(
        patient_id=user_id,
        doctor_name="Doctor Boysunov",
        appointment_date="2026-09-01",
        appointment_time="15:00",
        complaint="Test complaint",
    )
    runner.eq("create_status", appointment["status"], "pending")
    runner.eq("create_patient_id", appointment["patient_id"], user_id)

    patient_appointments = get_patient_appointments(user_id)
    runner.eq("get_patient_count", len(patient_appointments), 1)
    runner.eq("get_patient_first_id", patient_appointments[0]["id"], appointment["id"])

    confirmed = update_status(appointment["id"], "confirmed")
    runner.eq("update_status", confirmed["status"], "confirmed")

    cancelled = cancel_appointment(appointment["id"])
    runner.eq("cancel_status", cancelled["status"], "cancelled")

    triggers = [
        ("I want an appointment", True),
        ("Navbat olmoqchiman", True),
        ("Qabulga yoziling", True),
        ("Salom, qandaysiz?", False),
    ]
    for idx, (text, expected) in enumerate(triggers):
        runner.eq(f"trigger_{idx}", is_booking_trigger(text), expected)

    context = FakeContext()
    ask_ai_calls: list = []

    def track_ask_ai(*args, **kwargs):
        ask_ai_calls.append({"args": args, "kwargs": kwargs})
        return "AI javobi"

    with patch("app.handlers.chat.ask_ai", side_effect=track_ask_ai):
        replies = asyncio.run(run_booking_flow(context))

    runner.true("booking_started", "to'liq ismingizni" in replies[0].lower())
    runner.true("booking_confirmed", "qabul qilindi" in replies[-1].lower())
    runner.eq("booking_no_ai", len(ask_ai_calls), 0)
    runner.true("booking_state_cleared", BOOKING_STATE_KEY not in context.user_data)

    saved = get_patient_appointments(user_id)
    runner.eq("booking_saved_count", len(saved), 2)
    latest = saved[0]
    runner.eq("booking_saved_date", latest["appointment_date"], "2026-08-15")
    runner.eq("booking_saved_time", latest["appointment_time"], "10:30")
    runner.eq("booking_saved_complaint", latest["complaint"], "Bosh og'rig'i va aylanish")
    runner.eq("booking_saved_status", latest["status"], "pending")

    profile = get_patient_profile(user_id)
    runner.true("profile_updated", profile is not None)
    if profile:
        runner.eq("profile_name", profile["full_name"], "Sardor Karimov")
        runner.eq("profile_phone", profile["phone_number"], "+998901112233")

    with get_connection() as conn:
        conversation_id = conn.execute(
            "SELECT id FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()["id"]
        message_count = conn.execute(
            "SELECT COUNT(*) AS count FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()["count"]

    runner.true("memory_messages_saved", message_count >= 14)

    history = get_last_messages(conversation_id, limit=20)
    runner.true("memory_has_user_messages", any(m["role"] == "user" for m in history))
    runner.true("memory_has_assistant_messages", any(m["role"] == "assistant" for m in history))

    normal_context = FakeContext()
    ask_ai_calls.clear()
    with patch("app.handlers.chat.ask_ai", side_effect=track_ask_ai):
        normal_reply = asyncio.run(send_chat("Bugun ob-havo qanday?", normal_context))
    runner.eq("normal_chat_ai_called", len(ask_ai_calls), 1)
    runner.eq("normal_chat_reply", normal_reply, "AI javobi")

    if LEGACY_DB.exists():
        LEGACY_DB.unlink()
    legacy_conn = sqlite3.connect(LEGACY_DB)
    legacy_conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            full_name TEXT,
            created_at TEXT
        );
        """
    )
    legacy_conn.commit()
    legacy_conn.close()

    os.environ["DATABASE_PATH"] = str(LEGACY_DB)
    from importlib import reload
    import app.config as app_config
    import app.db.connection as db_connection
    import app.settings as app_settings

    app_settings.get_settings.cache_clear()
    reload(app_settings)
    reload(app_config)
    reload(db_connection)
    db_connection.init_db()

    with db_connection.get_connection() as conn:
        legacy_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    runner.true("legacy_migration_appointments", "appointments" in legacy_tables)
    os.environ["DATABASE_PATH"] = str(TEST_DB)
    app_settings.get_settings.cache_clear()
    reload(app_settings)
    reload(app_config)
    reload(db_connection)

    print()
    print("=" * 72)
    print(f"PHASE 5 STEP 1 VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)

    print("Phase 5 Step 1 OK: appointment booking system verified")
    print("=" * 72)


if __name__ == "__main__":
    main()

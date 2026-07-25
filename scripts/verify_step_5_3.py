"""Phase 5 Step 3: appointment management verification."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_5_3.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ADMIN_TELEGRAM_IDS"] = "999001,999002"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "admin-appt-test-token")
os.environ.setdefault("OPENAI_API_KEY", "admin-appt-test-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.db.connection import get_connection, init_db  # noqa: E402
from app.handlers.admin_appointments import (  # noqa: E402
    admin_appointments,
    admin_cancel_appt,
    admin_confirm,
    admin_note,
    admin_pending,
    admin_reschedule,
    admin_today,
)
from app.repositories.appointment_repository import (  # noqa: E402
    add_admin_notes,
    cancel_appointment,
    confirm_appointment,
    create_appointment,
    get_appointment,
    list_appointments_by_status,
    list_appointments_for_date,
    reschedule_appointment,
)
from app.repositories.conversation_repository import upsert_user  # noqa: E402
from app.services.admin_auth import is_admin  # noqa: E402
from app.services.appointment_dates import clinic_today_iso  # noqa: E402
from app.services.appointment_notifications import (  # noqa: E402
    notify_admins_new_appointment,
    notify_patient_appointment_cancelled,
    notify_patient_appointment_confirmed,
    notify_patient_appointment_rescheduled,
)


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

    def in_(self, name: str, needle: str, haystack: str) -> None:
        self.check(name, needle in haystack, f"{needle!r} not in {haystack!r}")


class FakeUser:
    def __init__(self, user_id: int, username: str = "user") -> None:
        self.id = user_id
        self.username = username
        self.full_name = "Test User"


class FakeMessage:
    def __init__(self) -> None:
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, user_id: int) -> None:
        self.effective_user = FakeUser(user_id)
        self.message = FakeMessage()


class FakeContext:
    def __init__(self, args: list[str] | None = None) -> None:
        self.args = args or []
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()


async def run_admin(command, update: FakeUpdate, context: FakeContext) -> str:
    await command(update, context)
    return update.message.reply_text.await_args.args[0]


def main() -> None:
    runner = TestRunner()
    init_db()

    with get_connection() as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(appointments)").fetchall()
        }

    for column in ("confirmation_time", "confirmed_by", "admin_notes", "updated_at"):
        runner.true(f"schema_column_{column}", column in columns)

    runner.true("admin_auth", is_admin(999001))
    runner.check("non_admin_denied", not is_admin(123), "")

    patient_user_id = upsert_user(telegram_id=810001, username="patient", full_name="Patient One")
    today = clinic_today_iso()

    appointment = create_appointment(
        patient_id=patient_user_id,
        doctor_name="Doctor Boysunov",
        appointment_date=today,
        appointment_time="11:00",
        complaint="Headache",
    )
    runner.eq("create_status_pending", appointment["status"], "pending")
    runner.true("create_updated_at", appointment["updated_at"] is not None)

    confirmed = confirm_appointment(appointment["id"], confirmed_by="admin:999001")
    runner.eq("confirm_status", confirmed["status"], "confirmed")
    runner.true("confirm_time_set", confirmed["confirmation_time"] is not None)
    runner.eq("confirm_by", confirmed["confirmed_by"], "admin:999001")

    rescheduled = reschedule_appointment(
        appointment["id"],
        appointment_date=today,
        appointment_time="15:30",
        updated_by="admin:999001",
    )
    runner.eq("reschedule_time", rescheduled["appointment_time"], "15:30")
    runner.true("reschedule_updated_at", rescheduled["updated_at"] is not None)

    noted = add_admin_notes(appointment["id"], "Patient prefers morning slot")
    runner.in_("admin_notes_saved", "morning slot", noted["admin_notes"] or "")

    pending = list_appointments_by_status("pending")
    confirmed_list = list_appointments_by_status("confirmed")
    runner.eq("pending_after_confirm", len(pending), 0)
    runner.eq("confirmed_list_count", len(confirmed_list), 1)

    today_list = list_appointments_for_date(today)
    runner.eq("today_list_count", len(today_list), 1)

    admin_context = FakeContext()
    admin_update = FakeUpdate(999001)
    reply = asyncio.run(run_admin(admin_pending, admin_update, admin_context))
    runner.in_("admin_pending_reply", "Kutilayotgan", reply)

    admin_update = FakeUpdate(999001)
    reply = asyncio.run(run_admin(admin_today, admin_update, admin_context))
    runner.in_("admin_today_reply", today, reply)

    admin_update = FakeUpdate(999001)
    reply = asyncio.run(run_admin(admin_appointments, admin_update, admin_context))
    runner.in_("admin_all_reply", "#", reply)

    non_admin_update = FakeUpdate(123)
    reply = asyncio.run(run_admin(admin_pending, non_admin_update, admin_context))
    runner.in_("non_admin_message", "administrator", reply.lower())

    bot = FakeContext().bot
    pending_appt = create_appointment(
        patient_id=patient_user_id,
        doctor_name="Doctor Boysunov",
        appointment_date=today,
        appointment_time="09:00",
        complaint="Follow-up",
    )
    sent = asyncio.run(
        notify_admins_new_appointment(
            bot,
            pending_appt,
            patient_profile={"full_name": "Patient One", "phone_number": "+998901234567"},
        )
    )
    runner.eq("admin_notify_count", sent, 2)
    runner.eq("admin_notify_calls", bot.send_message.await_count, 2)

    bot = FakeContext().bot
    asyncio.run(notify_patient_appointment_confirmed(bot, confirmed))
    runner.eq("patient_confirm_notify", bot.send_message.await_args.kwargs["chat_id"], 810001)

    bot = FakeContext().bot
    asyncio.run(
        notify_patient_appointment_rescheduled(
            bot,
            rescheduled,
            previous_date=today,
            previous_time="11:00",
        )
    )
    runner.in_(
        "patient_reschedule_notify",
        "o'zgartirildi",
        bot.send_message.await_args.kwargs["text"].lower(),
    )

    cancelled = cancel_appointment(appointment["id"], cancelled_by="admin:999001")
    runner.eq("cancel_status", cancelled["status"], "cancelled")

    bot = FakeContext().bot
    asyncio.run(notify_patient_appointment_cancelled(bot, cancelled))
    runner.in_(
        "patient_cancel_notify",
        "bekor qilindi",
        bot.send_message.await_args.kwargs["text"].lower(),
    )

    bot = FakeContext().bot
    admin_update = FakeUpdate(999001)
    admin_context = FakeContext(args=[str(pending_appt["id"])])
    admin_context.bot = bot
    reply = asyncio.run(run_admin(admin_confirm, admin_update, admin_context))
    runner.in_("admin_confirm_command", "tasdiqlandi", reply.lower())
    runner.eq("admin_confirm_patient_notify", bot.send_message.await_count, 1)

    fresh = create_appointment(
        patient_id=patient_user_id,
        doctor_name="Doctor Boysunov",
        appointment_date=today,
        appointment_time="16:00",
        complaint="Checkup",
    )
    bot = FakeContext().bot
    admin_update = FakeUpdate(999001)
    admin_context = FakeContext(args=[str(fresh["id"]), today, "17:00"])
    admin_context.bot = bot
    reply = asyncio.run(run_admin(admin_reschedule, admin_update, admin_context))
    runner.in_("admin_reschedule_command", "yangilandi", reply.lower())

    fresh2 = create_appointment(
        patient_id=patient_user_id,
        doctor_name="Doctor Boysunov",
        appointment_date=today,
        appointment_time="18:00",
        complaint="Cancel me",
    )
    bot = FakeContext().bot
    admin_update = FakeUpdate(999001)
    admin_context = FakeContext(args=[str(fresh2["id"])])
    admin_context.bot = bot
    reply = asyncio.run(run_admin(admin_cancel_appt, admin_update, admin_context))
    runner.in_("admin_cancel_command", "bekor qilindi", reply.lower())

    bot = FakeContext().bot
    admin_update = FakeUpdate(999001)
    admin_context = FakeContext(args=[str(fresh2["id"]), "Called", "patient"])
    admin_context.bot = bot
    reply = asyncio.run(run_admin(admin_note, admin_update, admin_context))
    runner.in_("admin_note_command", "eslatma", reply.lower())
    stored = get_appointment(fresh2["id"])
    runner.in_("admin_note_persisted", "Called patient", stored["admin_notes"] if stored else "")

    print()
    print("=" * 72)
    print(f"PHASE 5 STEP 3 VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)

    print("Phase 5 Step 3 OK: appointment management verified")
    print("=" * 72)


if __name__ == "__main__":
    main()

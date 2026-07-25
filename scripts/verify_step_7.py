"""Phase 7: unified communication engine verification."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_7.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ADMIN_TELEGRAM_IDS"] = "999001"
os.environ["SMS_ENABLED"] = "true"
os.environ["PUSH_ENABLED"] = "true"
os.environ["EMAIL_ENABLED"] = "true"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "comm-test-token")
os.environ.setdefault("OPENAI_API_KEY", "comm-test-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.db.connection import get_connection, init_db  # noqa: E402
from app.domain.communication import TELEGRAM_FAILURE_FALLBACK  # noqa: E402
from app.handlers.admin_communications import admin_comm_history, admin_resend_comm  # noqa: E402
from app.repositories.communication_repository import list_patient_channels  # noqa: E402
from app.repositories.conversation_repository import upsert_user  # noqa: E402
from app.repositories.follow_up_repository import list_due_follow_ups  # noqa: E402
from app.repositories.patient_profile_repository import update_patient_profile  # noqa: E402
from app.services.communication.channels import build_attempt_order, sync_patient_channels  # noqa: E402
from app.services.communication.service import (  # noqa: E402
    get_patient_communication_history,
    record_patient_reply,
    resend_delivery,
    send_patient_message,
)
from app.services.follow_up_planner import start_patient_follow_up_schedule  # noqa: E402
from app.services.follow_up_processor import notify_patient_follow_up, process_due_follow_ups  # noqa: E402
from app.services.appointment_notifications import notify_patient_appointment_confirmed  # noqa: E402
from app.repositories.appointment_repository import create_appointment  # noqa: E402


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
    id = 999001
    username = "admin"
    full_name = "Admin User"


class FakeMessage:
    def __init__(self) -> None:
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self) -> None:
        self.effective_user = FakeUser()
        self.message = FakeMessage()


class FakeContext:
    def __init__(self, bot: MagicMock) -> None:
        self.args: list[str] = []
        self.bot = bot


def _seed_patient(
    *,
    telegram_id: int,
    phone: str,
    email: str | None = None,
    push_token: str | None = None,
) -> int:
    patient_id = upsert_user(
        telegram_id=telegram_id,
        username="patient",
        full_name="Comm Patient",
    )
    fields = {"phone_number": phone}
    if email:
        fields["email"] = email
    if push_token:
        fields["mobile_push_token"] = push_token
    update_patient_profile(patient_id, **fields)
    sync_patient_channels(patient_id)
    return patient_id


async def main_async(runner: TestRunner) -> None:
    init_db()

    with get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    runner.check("table_patient_channels", "patient_communication_channels" in tables, repr(tables))
    runner.check("table_comm_deliveries", "communication_deliveries" in tables, repr(tables))

    runner.eq(
        "telegram_fallback_order",
        TELEGRAM_FAILURE_FALLBACK,
        ("sms", "mobile_push", "email"),
    )
    runner.eq(
        "attempt_order_all_channels",
        build_attempt_order({"telegram", "mobile_push", "sms", "email"}),
        ["telegram", "sms", "mobile_push", "email"],
    )
    runner.eq(
        "attempt_order_without_telegram",
        build_attempt_order({"mobile_push", "sms", "email"}),
        ["mobile_push", "sms", "email"],
    )

    patient_id = _seed_patient(
        telegram_id=950001,
        phone="901234567",
        email="patient@example.com",
        push_token="push-token-abc",
    )
    channels = list_patient_channels(patient_id)
    channel_names = {item["channel"] for item in channels}
    runner.check(
        "channels_stored_in_profile",
        channel_names == {"telegram", "sms", "email", "mobile_push"},
        repr(channel_names),
    )

    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=101))

    result = await send_patient_message(
        patient_id=patient_id,
        text="Test follow-up reminder",
        source_type="follow_up",
        source_id="1",
        bot=bot,
    )
    runner.true = lambda name, value: runner.check(name, bool(value), repr(value))
    runner.true("telegram_send_success", result.success)
    runner.eq("telegram_channel_used", result.channel, "telegram")
    runner.eq("telegram_status", result.status, "delivered")

    history = get_patient_communication_history(patient_id)
    runner.check("delivery_history_saved", len(history) >= 1, repr(history))
    runner.eq("latest_delivery_status", history[-1]["status"], "delivered")

    replied = record_patient_reply(delivery_id=history[-1]["id"], reply_text="Rahmat")
    runner.eq("reply_status", replied["status"], "replied")
    runner.eq("reply_text_saved", replied["reply_text"], "Rahmat")

    # Telegram fails -> SMS fallback
    sms_patient = _seed_patient(telegram_id=950002, phone="909876543")
    bot_fail = MagicMock()
    bot_fail.send_message = AsyncMock(side_effect=RuntimeError("telegram down"))

    sms_result = await send_patient_message(
        patient_id=sms_patient,
        text="Fallback SMS message",
        source_type="reminder",
        source_id="2",
        bot=bot_fail,
    )
    runner.true("sms_fallback_success", sms_result.success)
    runner.eq("sms_fallback_channel", sms_result.channel, "sms")
    runner.check(
        "sms_fallback_attempted_telegram_first",
        sms_result.attempted_channels[0] == "telegram",
        repr(sms_result.attempted_channels),
    )

    sms_history = get_patient_communication_history(sms_patient)
    failed_telegram = [item for item in sms_history if item["channel"] == "telegram"]
    runner.check("telegram_failure_logged", any(item["status"] == "failed" for item in failed_telegram), "")

    # Follow-up processor integration
    follow_patient = upsert_user(telegram_id=950003, username="fup", full_name="Follow Up")
    update_patient_profile(follow_patient, phone_number="901111222")
    sync_patient_channels(follow_patient)
    start_patient_follow_up_schedule(patient_id=follow_patient, started_at="2026-01-01")

    due = list_due_follow_ups(as_of_date="2026-01-11")
    runner.check("due_follow_up_exists", len(due) >= 1, repr(due))

    follow_bot = MagicMock()
    follow_bot.send_message = AsyncMock(return_value=MagicMock(message_id=202))
    notified = await notify_patient_follow_up(follow_bot, due[0])
    runner.true("follow_up_notify_via_unified_service", notified)

    sent_count = await process_due_follow_ups(follow_bot, as_of_date="2026-01-11")
    runner.check("process_due_follow_ups_runs", sent_count >= 0, str(sent_count))

    # Appointment notification integration
    appointment = create_appointment(
        patient_id=patient_id,
        doctor_name="Dr Boysunov",
        appointment_date="2026-04-01",
        appointment_time="10:00",
        complaint="Test",
    )
    appt_bot = MagicMock()
    appt_bot.send_message = AsyncMock(return_value=MagicMock(message_id=303))
    appt_sent = await notify_patient_appointment_confirmed(appt_bot, appointment)
    runner.true("appointment_notification_sent", appt_sent)

    appt_history = get_patient_communication_history(patient_id, source_type="appointment")
    runner.check("appointment_delivery_logged", len(appt_history) >= 1, repr(appt_history))

    # Admin resend
    delivery_id = appt_history[-1]["id"]
    resend_bot = MagicMock()
    resend_bot.send_message = AsyncMock(return_value=MagicMock(message_id=404))

    async def run_resend() -> str:
        update = FakeUpdate()
        context = FakeContext(resend_bot)
        context.args = [str(delivery_id)]
        await admin_resend_comm(update, context)
        return update.message.reply_text.await_args.args[0]

    resend_reply = await run_resend()
    runner.check("admin_resend_success", "qayta yuborildi" in resend_reply.lower(), resend_reply)

    async def run_history() -> str:
        update = FakeUpdate()
        context = FakeContext(resend_bot)
        context.args = [str(patient_id)]
        await admin_comm_history(update, context)
        return update.message.reply_text.await_args.args[0]

    history_reply = await run_resend()
    _ = history_reply
    history_admin_reply = await run_history()
    runner.check("admin_history_lists_deliveries", "xabarlar tarixi" in history_admin_reply, history_admin_reply)

    manual_resend = await resend_delivery(delivery_id=delivery_id, bot=resend_bot)
    runner.true("programmatic_resend", manual_resend.success)

    # Persistence
    init_db()
    reloaded = get_patient_communication_history(patient_id)
    runner.check("history_survives_restart", len(reloaded) >= 3, str(len(reloaded)))

    with get_connection() as conn:
        delivery_count = conn.execute(
            "SELECT COUNT(*) AS c FROM communication_deliveries WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()["c"]
    runner.check("deliveries_persisted", delivery_count >= 3, str(delivery_count))


def main() -> None:
    runner = TestRunner()
    asyncio.run(main_async(runner))

    print()
    print("=" * 72)
    print(f"PHASE 7 VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)

    print("Phase 7 OK: unified communication engine verified")
    print("=" * 72)


if __name__ == "__main__":
    main()

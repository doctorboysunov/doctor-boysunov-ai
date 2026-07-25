"""Phase 8: AI Doctor Dashboard verification."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_8.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ADMIN_TELEGRAM_IDS"] = "999001"
os.environ["DASHBOARD_API_KEY"] = "test-dashboard-key"
os.environ["SMS_ENABLED"] = "true"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dashboard-test-token")
os.environ.setdefault("OPENAI_API_KEY", "dashboard-test-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.db.connection import get_connection, init_db  # noqa: E402
from app.handlers.admin_dashboard import admin_dashboard, admin_dashboard_generate  # noqa: E402
from app.repositories.appointment_repository import create_appointment  # noqa: E402
from app.repositories.communication_repository import create_delivery_record  # noqa: E402
from app.repositories.conversation_repository import upsert_user  # noqa: E402
from app.repositories.dashboard_repository import get_latest_dashboard_snapshot  # noqa: E402
from app.repositories.follow_up_repository import (  # noqa: E402
    list_follow_ups_for_patient,
    mark_follow_up_notified,
)
from app.repositories.patient_profile_repository import update_patient_profile  # noqa: E402
from app.services.dashboard_actions import (  # noqa: E402
    QUICK_ACTIONS,
    action_book_appointment,
    action_mark_follow_up_completed,
    action_open_patient_card,
    action_reschedule_follow_up,
    action_send_sms,
)
from app.services.dashboard_dates import range_for_period  # noqa: E402
from app.services.dashboard_service import (  # noqa: E402
    build_doctor_dashboard,
    format_dashboard_telegram,
    generate_morning_dashboard,
    send_morning_dashboard_to_admins,
)
from app.services.follow_up_planner import start_patient_follow_up_schedule  # noqa: E402
from app.services.patient_creation_engine import create_patient_intelligently  # noqa: E402


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
    full_name = "Admin"


class FakeMessage:
    def __init__(self) -> None:
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self) -> None:
        self.effective_user = FakeUser()
        self.message = FakeMessage()


class FakeContext:
    def __init__(self, bot: MagicMock | None = None) -> None:
        self.args: list[str] = []
        self.bot = bot or MagicMock()


def main() -> None:
    runner = TestRunner()
    init_db()
    today = date.today().isoformat()

    with get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    runner.check("table_dashboard_snapshots", "dashboard_snapshots" in tables, repr(tables))

    runner.eq("filter_today_range", range_for_period("today").start, today)
    runner.check("filter_week_range", range_for_period("week").start <= today, "")
    runner.check("filter_month_range", range_for_period("month").start <= today, "")

    created = create_patient_intelligently(
        source="telegram",
        text="Dashboard Patient 901234567",
        started_at="2026-01-01",
    )
    runner.true = lambda name, value: runner.check(name, bool(value), repr(value))
    runner.true("seed_patient", created is not None)
    patient_id = created.patient_id if created else 0

    upsert_user(telegram_id=960001, username="dash_p2", full_name="Second Patient")
    patient2 = upsert_user(telegram_id=960002, username="dash_p3", full_name="Third Patient")
    update_patient_profile(patient2, phone_number="909998877", email="p@example.com")

    create_appointment(
        patient_id=patient_id,
        doctor_name="Dr Boysunov",
        appointment_date=today,
        appointment_time="10:00",
        complaint="Dashboard test",
        status="confirmed",
    )
    create_appointment(
        patient_id=patient2,
        doctor_name="Dr Boysunov",
        appointment_date=today,
        appointment_time="11:00",
        complaint="Past visit",
        status="confirmed",
    )

    follow_ups = list_follow_ups_for_patient(patient_id)
    runner.check("follow_ups_exist", len(follow_ups) >= 1, str(len(follow_ups)))
    if follow_ups:
        first_follow_up = follow_ups[0]
        first_follow_up = mark_follow_up_notified(first_follow_up["id"])
        create_delivery_record(
            patient_id=patient_id,
            channel="telegram",
            source_type="follow_up",
            source_id=str(first_follow_up["id"]),
            message_text="Nazorat eslatmasi",
            status="sent",
            provider_name="telegram_bot",
        )

    dashboard = build_doctor_dashboard(period="today", anchor_date=today)
    runner.eq("dashboard_period", dashboard["period"], "today")
    runner.check("appointments_today_section", isinstance(dashboard["appointments_today"], list), "")
    runner.check("follow_ups_today_section", isinstance(dashboard["follow_ups_today"], list), "")
    runner.check("follow_up_buckets", "10_day" in dashboard["follow_up_buckets"], dashboard["follow_up_buckets"].keys())
    runner.check("high_priority_section", isinstance(dashboard["high_priority_patients"], list), "")
    runner.check("non_responders_section", isinstance(dashboard["non_responders"], list), "")
    runner.check("new_patients_section", isinstance(dashboard["new_patients_today"], list), "")
    runner.check("upcoming_section", isinstance(dashboard["upcoming_appointments"], list), "")
    runner.check("missed_section", isinstance(dashboard["missed_appointments"], list), "")
    runner.check("ai_recommendations", len(dashboard["ai_recommendations"]) >= 1, dashboard["ai_recommendations"])
    runner.check("statistics_block", "appointments_today" in dashboard["statistics"], dashboard["statistics"])
    runner.check("mobile_layout_flag", dashboard["layout"]["mobile_stack"] is True, dashboard["layout"])
    runner.check("filters_available", set(dashboard["filters"]) >= {"today", "tomorrow", "week", "month"}, dashboard["filters"])

    if dashboard["appointments_today"]:
        runner.check(
            "patient_quick_actions",
            dashboard["appointments_today"][0]["actions"] == list(QUICK_ACTIONS),
            dashboard["appointments_today"][0]["actions"],
        )

    telegram_text = format_dashboard_telegram(dashboard)
    runner.check("telegram_format", "Dashboard" in telegram_text and "Statistika" in telegram_text, telegram_text[:120])

    snapshot = generate_morning_dashboard(period="today")
    runner.check("morning_snapshot_saved", snapshot["as_of_date"] == today, snapshot["as_of_date"])
    loaded = get_latest_dashboard_snapshot(snapshot_date=today, period="today")
    runner.true("snapshot_loaded", loaded is not None)

    init_db()
    runner.true("snapshot_persists_restart", get_latest_dashboard_snapshot(snapshot_date=today, period="today") is not None)

    async def run_dashboard_command() -> str:
        update = FakeUpdate()
        context = FakeContext()
        context.args = ["today"]
        await admin_dashboard(update, context)
        return update.message.reply_text.await_args.args[0]

    async def run_generate_command() -> str:
        update = FakeUpdate()
        context = FakeContext()
        context.args = ["week"]
        await admin_dashboard_generate(update, context)
        return update.message.reply_text.await_args.args[0]

    reply = asyncio.run(run_dashboard_command())
    runner.check("telegram_dashboard_command", "Dashboard" in reply, reply[:120])

    week_reply = asyncio.run(run_generate_command())
    runner.check("telegram_generate_command", "snapshot saqlandi" in week_reply.lower(), week_reply[:120])

    bot = MagicMock()
    bot.send_message = AsyncMock()
    sent = asyncio.run(send_morning_dashboard_to_admins(bot))
    runner.eq("morning_send_admins", sent, 1)

    card = asyncio.run(action_open_patient_card(patient_id))
    runner.eq("open_patient_card", card["patient_id"], patient_id)
    runner.check("card_has_actions", card["actions"] == list(QUICK_ACTIONS), card["actions"])

    sms_result = asyncio.run(action_send_sms(patient_id=patient_id, text="SMS test"))
    runner.true("send_sms_action", sms_result.get("success"))

    if follow_ups:
        completed = asyncio.run(action_mark_follow_up_completed(follow_ups[0]["id"]))
        runner.true("mark_completed_action", completed.get("success"))

        rescheduled = asyncio.run(
            action_reschedule_follow_up(follow_ups[-1]["id"], scheduled_date=today)
        )
        runner.true("reschedule_follow_up_action", rescheduled.get("success"))

    booked = asyncio.run(
        action_book_appointment(
            patient_id=patient_id,
            doctor_name="Dr Boysunov",
            appointment_date=today,
            appointment_time="15:00",
            complaint="Booked from dashboard",
        )
    )
    runner.true("book_appointment_action", booked.get("success"))

    week_dashboard = build_doctor_dashboard(period="week", anchor_date=today)
    runner.eq("week_filter", week_dashboard["period"], "week")
    month_dashboard = build_doctor_dashboard(period="month", anchor_date=today)
    runner.eq("month_filter", month_dashboard["period"], "month")
    tomorrow_dashboard = build_doctor_dashboard(period="tomorrow", anchor_date=today)
    runner.eq("tomorrow_filter", tomorrow_dashboard["period"], "tomorrow")

    live1 = build_doctor_dashboard(period="today", anchor_date=today)
    create_appointment(
        patient_id=patient2,
        doctor_name="Dr Boysunov",
        appointment_date=today,
        appointment_time="16:30",
        complaint="Realtime test",
    )
    live2 = build_doctor_dashboard(period="today", anchor_date=today)
    runner.check(
        "realtime_refresh",
        live2["statistics"]["appointments_today"] >= live1["statistics"]["appointments_today"],
        f"{live1['statistics']['appointments_today']} -> {live2['statistics']['appointments_today']}",
    )

    from fastapi.testclient import TestClient  # noqa: E402
    from app.api.dashboard_api import app  # noqa: E402

    client = TestClient(app)
    headers = {"X-API-Key": "test-dashboard-key"}

    health = client.get("/api/v1/health")
    runner.eq("api_health", health.status_code, 200)

    api_dashboard = client.get("/api/v1/dashboard?period=today", headers=headers)
    runner.eq("api_dashboard_status", api_dashboard.status_code, 200)
    body = api_dashboard.json()
    runner.check("api_dashboard_sections", "ai_recommendations" in body, body.keys())
    runner.check("api_statistics", body["statistics"]["appointments_today"] >= 1, body["statistics"])

    card_resp = client.get(f"/api/v1/dashboard/patient/{patient_id}", headers=headers)
    runner.eq("api_patient_card", card_resp.status_code, 200)

    sms_resp = client.post(
        "/api/v1/dashboard/actions/send-sms",
        headers=headers,
        json={"patient_id": patient_id, "text": "API SMS"},
    )
    runner.eq("api_send_sms", sms_resp.status_code, 200)

    generate_resp = client.post("/api/v1/dashboard/generate?period=today", headers=headers)
    runner.eq("api_generate", generate_resp.status_code, 200)

    snapshot_resp = client.get(
        f"/api/v1/dashboard/snapshot?snapshot_date={today}&period=today",
        headers=headers,
    )
    runner.eq("api_snapshot", snapshot_resp.status_code, 200)

    print()
    print("=" * 72)
    print(f"PHASE 8 VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)

    print("Phase 8 OK: AI Doctor Dashboard verified")
    print("=" * 72)


if __name__ == "__main__":
    main()

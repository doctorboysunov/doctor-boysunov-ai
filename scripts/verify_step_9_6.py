"""Phase 9.6: AI Care Manager verification."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_9_6.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ADMIN_TELEGRAM_IDS"] = "999001"
os.environ["DASHBOARD_API_KEY"] = "test-care-manager-key"
os.environ["SMS_ENABLED"] = "true"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "care-manager-test-token")
os.environ.setdefault("OPENAI_API_KEY", "care-manager-test-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from fastapi.testclient import TestClient  # noqa: E402

from app.api.dashboard_api import app as dashboard_app  # noqa: E402
from app.db.connection import get_connection, init_db  # noqa: E402
from app.repositories.care_manager_repository import list_care_manager_records_for_patient  # noqa: E402
from app.repositories.communication_repository import get_pending_follow_up_reply_delivery  # noqa: E402
from app.repositories.follow_up_repository import (  # noqa: E402
    get_follow_up,
    list_follow_ups_for_patient,
    mark_follow_up_notified,
)
from app.repositories.patient_profile_repository import update_patient_profile  # noqa: E402
from app.services.care_manager_processor import process_care_manager_no_responses  # noqa: E402
from app.services.care_manager_service import classify_patient_reply  # noqa: E402
from app.services.dashboard_service import build_doctor_dashboard  # noqa: E402
from app.services.emr_service import build_patient_emr  # noqa: E402
from app.services.follow_up_messages import (  # noqa: E402
    CHECK_IN_MESSAGE,
    build_care_manager_message,
    messages_contain_prescription_language,
)
from app.services.follow_up_processor import process_due_follow_ups  # noqa: E402
from app.services.follow_up_reply_service import handle_follow_up_patient_reply  # noqa: E402
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
    def __init__(self, user_id: int) -> None:
        self.id = user_id
        self.username = "patient"
        self.full_name = "Care Manager Patient"


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, user_id: int, text: str) -> None:
        self.effective_user = FakeUser(user_id)
        self.message = FakeMessage(text)


class FakeContext:
    def __init__(self, bot: MagicMock) -> None:
        self.bot = bot


def _set_notified_at(follow_up_id: int, notified_iso: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE follow_ups SET notified_at = ?, updated_at = ? WHERE id = ?",
            (notified_iso, notified_iso, follow_up_id),
        )
        conn.commit()


def main() -> None:
    runner = TestRunner()
    init_db()
    anchor = date(2026, 1, 1)

    msg_day10 = build_care_manager_message("check_in", sequence_number=1, scheduled_date="2026-01-11")
    runner.check("day10_message", CHECK_IN_MESSAGE.split(".")[0] in msg_day10, msg_day10[:80])
    runner.check("day20_message", "Og'riq kamayganmi" in build_care_manager_message("check_in", sequence_number=2, scheduled_date="2026-01-21"), "")
    runner.check("month3_invite", "3 oy" in build_care_manager_message("examination", sequence_number=4, scheduled_date="2026-04-01"), "")
    runner.check("month6_invite", "6 oy" in build_care_manager_message("preventive", sequence_number=5, scheduled_date="2026-07-01"), "")
    runner.check("no_prescriptions", not messages_contain_prescription_language(), "")

    runner.eq("classify_good", classify_patient_reply("Yaxshiman, og'riq kamaydi"), "good")
    runner.eq("classify_no_change", classify_patient_reply("Hech narsa o'zgarmadi"), "no_change")
    runner.eq("classify_worse", classify_patient_reply("Holatim yomonlashdi"), "worse")

    created = create_patient_intelligently(
        source="telegram",
        text="Care Manager Patient 901888001",
        started_at=anchor.isoformat(),
        telegram_id=710001,
    )
    runner.check("patient_created", created is not None, repr(created))
    if created is None:
        _report(runner)
        return

    patient_id = created.patient_id
    update_patient_profile(patient_id, phone_number="+998901888001")

    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    sent = asyncio.run(process_due_follow_ups(bot, as_of_date="2026-01-11"))
    runner.eq("day10_sent", sent, 1)

    records = list_care_manager_records_for_patient(patient_id)
    runner.check("emr_care_record_on_send", any(r["event_type"] == "check_in_sent" for r in records), repr(records))

    follow_up = list_follow_ups_for_patient(patient_id)[0]
    runner.eq("follow_up_notified", follow_up["status"], "notified")

    # GOOD reply
    update = FakeUpdate(710001, "Yaxshiman, og'riq kamaydi")
    handled = asyncio.run(
        handle_follow_up_patient_reply(update, FakeContext(bot), patient_id=patient_id, reply_text="Yaxshiman, og'riq kamaydi")
    )
    runner.true = lambda name, value: runner.check(name, bool(value), repr(value))
    runner.true("good_reply_handled", handled)
    runner.eq("good_outcome", get_follow_up(follow_up["id"])["response_outcome"], "good")
    runner.check("good_emr_record", any(r["outcome"] == "good" for r in list_care_manager_records_for_patient(patient_id)), "")

    # Day 20 — WORSE reply
    asyncio.run(process_due_follow_ups(bot, as_of_date="2026-01-21"))
    pending = get_pending_follow_up_reply_delivery(patient_id)
    runner.check("day20_pending_delivery", pending is not None, "")

    worse_update = FakeUpdate(710001, "Holatim yomonlashdi, bosh og'riyapti")
    asyncio.run(
        handle_follow_up_patient_reply(
            worse_update,
            FakeContext(bot),
            patient_id=patient_id,
            reply_text="Holatim yomonlashdi, bosh og'riyapti",
        )
    )
    worse_follow_up = [f for f in list_follow_ups_for_patient(patient_id) if f["sequence_number"] == 2][0]
    runner.eq("worse_outcome", worse_follow_up["response_outcome"], "worse")
    runner.true("worse_high_priority", bool(worse_follow_up["high_priority"]))
    worse_reply = worse_update.message.reply_text.await_args.args[0]
    runner.check("worse_recommends_booking", "Navbat olmoqchiman" in worse_reply, worse_reply)
    runner.true("doctor_alert_worse", bot.send_message.await_count >= 1)

    # NO RESPONSE workflow
    asyncio.run(process_due_follow_ups(bot, as_of_date="2026-01-31"))
    day30 = [f for f in list_follow_ups_for_patient(patient_id) if f["sequence_number"] == 3][0]
    old_notify = (date(2026, 1, 31) - timedelta(days=3)).isoformat() + "T10:00:00+00:00"
    _set_notified_at(day30["id"], old_notify)

    retry_result = asyncio.run(process_care_manager_no_responses(bot, as_of_date="2026-01-31"))
    runner.eq("retry_sent_once", retry_result["retried"], 1)
    runner.eq("day30_retry_count", get_follow_up(day30["id"])["retry_count"], 1)

    _set_notified_at(day30["id"], old_notify)
    get_follow_up(day30["id"])
    fu = get_follow_up(day30["id"])
    fu = get_follow_up(day30["id"])
    with get_connection() as conn:
        conn.execute("UPDATE follow_ups SET retry_count = 1 WHERE id = ?", (day30["id"],))
        conn.commit()

    mark_result = asyncio.run(process_care_manager_no_responses(bot, as_of_date="2026-01-31"))
    runner.eq("marked_no_response", mark_result["marked_no_response"], 1)
    runner.eq("no_response_status", get_follow_up(day30["id"])["status"], "no_response")
    runner.check(
        "no_response_emr",
        any(r["event_type"] == "no_response_marked" for r in list_care_manager_records_for_patient(patient_id)),
        "",
    )

    # Dashboard care manager sections
    dashboard = build_doctor_dashboard(period="month", anchor_date="2026-07-01")
    care = dashboard.get("care_manager") or {}
    runner.check("dashboard_improving", "patients_improving" in care, str(care.keys()))
    runner.check("dashboard_unchanged", "patients_unchanged" in care, "")
    runner.check("dashboard_worsening", "patients_worsening" in care, "")
    runner.check("dashboard_not_responding", "patients_not_responding" in care, "")
    runner.check("dashboard_followups_today", "follow_ups_today" in dashboard, "")
    runner.check("dashboard_upcoming_followups", "upcoming_follow_ups" in dashboard, "")
    runner.check("dashboard_has_worsening_patient", any(p["patient_id"] == patient_id for p in care.get("patients_worsening", [])), "")

    emr = build_patient_emr(patient_id)
    runner.check("emr_care_manager_records", len(emr["emr"].get("care_manager_records", [])) >= 3, "")
    runner.check("emr_timeline_care_events", any(e.get("event_type") == "care_manager" for e in emr["emr"]["timeline"]), "")

    client = TestClient(dashboard_app)
    api = client.get(
        "/api/v1/dashboard?period=month&anchor_date=2026-07-01",
        headers={"X-API-Key": "test-care-manager-key"},
    )
    runner.eq("dashboard_api_ok", api.status_code, 200)
    runner.check("api_care_manager", "care_manager" in api.json(), "")

    _report(runner)


def _report(runner: TestRunner) -> None:
    print()
    print("=" * 72)
    print(f"PHASE 9.6 AI CARE MANAGER: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Phase 9.6 OK: AI Care Manager verified")
    print("=" * 72)


if __name__ == "__main__":
    main()

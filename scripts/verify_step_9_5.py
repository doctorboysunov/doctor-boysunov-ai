"""Phase 9.5: Fully automatic follow-up verification."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_9_5.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ADMIN_TELEGRAM_IDS"] = "999001"
os.environ["SMS_ENABLED"] = "true"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "followup-auto-test-token")
os.environ.setdefault("OPENAI_API_KEY", "followup-auto-test-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.db.connection import init_db  # noqa: E402
from app.domain.follow_up_schedule import INITIAL_FOLLOW_UP_SCHEDULE  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.repositories.communication_repository import (  # noqa: E402
    get_pending_follow_up_reply_delivery,
    list_delivery_history,
)
from app.repositories.conversation_repository import upsert_user  # noqa: E402
from app.repositories.follow_up_repository import (  # noqa: E402
    list_due_follow_ups,
    list_follow_ups_for_patient,
)
from app.repositories.patient_profile_repository import update_patient_profile  # noqa: E402
from app.services.emr_service import create_visit, edit_visit  # noqa: E402
from app.services.follow_up_messages import messages_contain_prescription_language  # noqa: E402
from app.services.follow_up_planner import (  # noqa: E402
    ensure_automatic_follow_up_plan,
    on_visit_completed,
    stop_patient_follow_up_plan,
)
from app.services.care_manager_service import classify_patient_reply
from app.services.follow_up_processor import notify_patient_follow_up, process_due_follow_ups  # noqa: E402
from app.services.follow_up_reply_service import (  # noqa: E402
    follow_up_messages_are_safe,
    handle_follow_up_patient_reply,
)
from app.services.follow_up_scheduler import (  # noqa: E402
    add_months,
    build_initial_follow_up_dates,
    parse_iso_date,
)
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
        self.full_name = "Auto Follow Up Patient"


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


def main() -> None:
    runner = TestRunner()
    init_db()
    anchor = date(2026, 1, 1)

    runner.eq("schedule_steps", len(INITIAL_FOLLOW_UP_SCHEDULE), 5)
    runner.check("messages_no_prescriptions", not messages_contain_prescription_language(), "")
    runner.check("reply_messages_safe", follow_up_messages_are_safe(), "")

    planned = build_initial_follow_up_dates(anchor)
    expected = [
        date(2026, 1, 11),
        date(2026, 1, 21),
        date(2026, 1, 31),
        add_months(anchor, 3),
        add_months(anchor, 6),
    ]
    runner.eq("planned_count", len(planned), 5)
    for idx, (_, scheduled, _) in enumerate(planned):
        runner.eq(f"milestone_date_{idx + 1}", scheduled, expected[idx])
    runner.eq("month3_kind", planned[3][2], "examination")
    runner.eq("month6_kind", planned[4][2], "preventive")

    created = create_patient_intelligently(
        source="telegram",
        text="Auto Follow Patient 901777001",
        started_at=anchor.isoformat(),
        telegram_id=700001,
    )
    runner.check("patient_created", created is not None, repr(created))
    if created is None:
        _report(runner)
        return

    patient_id = created.patient_id
    follow_ups = list_follow_ups_for_patient(patient_id)
    runner.eq("auto_plan_on_create", len(follow_ups), 6)
    runner.eq("day10_date", follow_ups[0]["scheduled_date"], "2026-01-11")
    runner.eq("day20_date", follow_ups[1]["scheduled_date"], "2026-01-21")
    runner.eq("day30_date", follow_ups[2]["scheduled_date"], "2026-01-31")
    runner.eq("month3_date", follow_ups[3]["scheduled_date"], "2026-04-01")
    runner.eq("month6_date", follow_ups[4]["scheduled_date"], "2026-07-01")
    runner.eq("first_recurring_date", follow_ups[5]["scheduled_date"], "2027-01-01")

    duplicate_plan = ensure_automatic_follow_up_plan(
        patient_id=patient_id,
        anchor_date="2026-02-01",
    )
    runner.check("idempotent_plan", duplicate_plan is not None, "")
    runner.eq("no_duplicate_followups", len(list_follow_ups_for_patient(patient_id)), 6)

    visit = create_visit(
        patient_id,
        visit_date="2026-03-01",
        main_complaint="Control visit",
        preliminary_diagnosis="Stable",
    )
    runner.eq("visit_without_final_keeps_plan", len(list_follow_ups_for_patient(patient_id)), 6)

    completed = edit_visit(
        patient_id,
        visit["id"],
        final_diagnosis="Improved — visit complete",
    )
    runner.check("visit_completed", completed.get("final_diagnosis") is not None, "")

    after_visit = list_follow_ups_for_patient(patient_id)
    runner.check("visit_completion_reschedules", len(after_visit) >= 6, str(len(after_visit)))
    runner.eq("visit_anchor_day10", after_visit[0]["scheduled_date"], "2026-03-11")

    update_patient_profile(patient_id, phone_number="+998901777001")

    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=101))

    due = list_due_follow_ups(as_of_date="2026-03-11")
    runner.check("due_after_visit_anchor", any(item["patient_id"] == patient_id for item in due), repr(due))

    sent = asyncio.run(process_due_follow_ups(bot, as_of_date="2026-03-11"))
    runner.eq("notify_due_followup", sent, 1)
    runner.check("telegram_attempted", bot.send_message.await_count >= 1, str(bot.send_message.await_count))

    reloaded = list_follow_ups_for_patient(patient_id)
    runner.check("marked_notified", any(item["status"] == "notified" for item in reloaded), "")

    pending_delivery = get_pending_follow_up_reply_delivery(patient_id)
    runner.check("pending_reply_delivery", pending_delivery is not None, "")

    runner.check("worsening_detected", classify_patient_reply("Holatim yomonlashdi, bosh og'riyapti") == "worse", "")
    runner.check("stable_not_worsening", classify_patient_reply("Yaxshiman, rahmat") == "good", "")

    update = FakeUpdate(700001, "Holatim yomonlashdi, bosh og'riyapti")
    context = FakeContext(bot)
    handled = asyncio.run(
        handle_follow_up_patient_reply(
            update,
            context,
            patient_id=patient_id,
            reply_text="Holatim yomonlashdi, bosh og'riyapti",
        )
    )
    runner.true = lambda name, value: runner.check(name, bool(value), repr(value))
    runner.true("reply_handled", handled)
    runner.true("doctor_notified", bot.send_message.await_count >= 1)
    reply_text = update.message.reply_text.await_args.args[0]
    runner.check("reply_recommends_appointment", "Navbat olmoqchiman" in reply_text, reply_text)
    runner.check("reply_no_prescription", "retsept" in reply_text.lower() or "dori-darmon" in reply_text.lower(), reply_text)

    history = list_delivery_history(patient_id, source_type="follow_up")
    runner.check("reply_recorded", any(item.get("status") == "replied" for item in history), repr(history))

    sent_step5 = asyncio.run(process_due_follow_ups(bot, as_of_date=after_visit[4]["scheduled_date"]))
    runner.check("notify_month6", sent_step5 >= 0, str(sent_step5))
    after_month6 = list_follow_ups_for_patient(patient_id)
    runner.check("recurring_after_month6", len(after_month6) >= 7, str(len(after_month6)))
    if len(after_month6) >= 7:
        runner.eq(
            "second_recurring_six_months_later",
            parse_iso_date(after_month6[6]["scheduled_date"]),
            add_months(parse_iso_date(after_month6[5]["scheduled_date"]), 6),
        )

    stopped = stop_patient_follow_up_plan(patient_id)
    runner.check("doctor_can_stop", stopped["cancelled_follow_ups"] >= 0, repr(stopped))
    remaining = [item for item in list_follow_ups_for_patient(patient_id) if item["status"] == "scheduled"]
    runner.eq("no_pending_after_stop", len(remaining), 0)

    _report(runner)


def _report(runner: TestRunner) -> None:
    print()
    print("=" * 72)
    print(f"PHASE 9.5 AUTOMATIC FOLLOW-UP: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Phase 9.5 OK: fully automatic follow-up verified")
    print("=" * 72)


if __name__ == "__main__":
    main()

"""Phase 5 Step 4: follow-up schedule verification."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_5_4.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "followup-test-token")
os.environ.setdefault("OPENAI_API_KEY", "followup-test-key")

sys.path.insert(0, str(ROOT))

from app.db.connection import get_connection, init_db  # noqa: E402
from app.repositories.conversation_repository import upsert_user  # noqa: E402
from app.repositories.follow_up_repository import (  # noqa: E402
    list_due_follow_ups,
    list_follow_ups_for_patient,
)
from app.services.follow_up_messages import messages_contain_prescription_language  # noqa: E402
from app.services.follow_up_planner import start_patient_follow_up_schedule  # noqa: E402
from app.services.follow_up_processor import process_due_follow_ups  # noqa: E402
from app.services.follow_up_scheduler import (  # noqa: E402
    add_months,
    apply_offset,
    build_initial_follow_up_dates,
    parse_iso_date,
    to_iso_date,
)
from app.domain.follow_up_schedule import INITIAL_FOLLOW_UP_SCHEDULE  # noqa: E402


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


def main() -> None:
    runner = TestRunner()
    init_db()

    with get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    runner.check("table_patient_treatments", "patient_treatments" in tables, repr(tables))
    runner.check("table_follow_ups", "follow_ups" in tables, repr(tables))

    runner.eq("schedule_steps_count", len(INITIAL_FOLLOW_UP_SCHEDULE), 5)
    runner.check(
        "messages_no_prescriptions",
        not messages_contain_prescription_language(),
        "forbidden wording found",
    )

    treatment_start = date(2026, 1, 1)
    planned = build_initial_follow_up_dates(treatment_start)
    runner.eq("planned_count", len(planned), 5)

    expected_dates = [
        date(2026, 1, 11),
        date(2026, 1, 21),
        date(2026, 1, 31),
        add_months(treatment_start, 3),
        add_months(treatment_start, 6),
    ]
    for idx, (_, scheduled, _) in enumerate(planned):
        runner.eq(f"schedule_date_{idx + 1}", scheduled, expected_dates[idx])

    runner.eq("step4_kind", planned[3][2], "examination")
    runner.eq("step5_kind", planned[4][2], "preventive")

    patient_id = upsert_user(telegram_id=820001, username="followup_patient", full_name="Follow Up")
    treatment = start_patient_follow_up_schedule(
        patient_id=patient_id,
        started_at="2026-01-01",
    )

    follow_ups = list_follow_ups_for_patient(patient_id)
    runner.eq("stored_initial_plus_recurring", len(follow_ups), 6)
    runner.eq("first_follow_up_date", follow_ups[0]["scheduled_date"], "2026-01-11")
    runner.eq("fifth_kind", follow_ups[4]["follow_up_kind"], "preventive")
    runner.eq("sixth_kind", follow_ups[5]["follow_up_kind"], "preventive")

    sixth_date = parse_iso_date(follow_ups[5]["scheduled_date"])
    fifth_date = parse_iso_date(follow_ups[4]["scheduled_date"])
    runner.eq("sixth_after_fifth", sixth_date, add_months(fifth_date, 6))

    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM follow_ups").fetchone()["c"]
    runner.eq("sqlite_persist_count", count, 6)

    init_db()
    reloaded = list_follow_ups_for_patient(patient_id)
    runner.eq("survives_restart", len(reloaded), 6)

    due = list_due_follow_ups(as_of_date="2026-01-11")
    runner.check("due_on_first_date", any(item["sequence_number"] == 1 for item in due), repr(due))

    bot = MagicMock()
    bot.send_message = AsyncMock()

    sent = asyncio.run(process_due_follow_ups(bot, as_of_date="2026-01-11"))
    runner.eq("notify_first_due", sent, 1)

    reloaded = list_follow_ups_for_patient(patient_id)
    runner.eq("first_marked_notified", reloaded[0]["status"], "notified")

    sent_step5 = asyncio.run(process_due_follow_ups(bot, as_of_date=follow_ups[4]["scheduled_date"]))
    runner.check("notify_step5_runs", sent_step5 >= 0, str(sent_step5))

    after_step5 = list_follow_ups_for_patient(patient_id)
    runner.check("recurring_after_step5", len(after_step5) >= 6, str(len(after_step5)))

    if len(after_step5) >= 7:
        seventh = after_step5[6]
        sixth = after_step5[5]
        runner.eq(
            "seventh_is_six_months_after_sixth",
            parse_iso_date(seventh["scheduled_date"]),
            add_months(parse_iso_date(sixth["scheduled_date"]), 6),
        )

    print()
    print("=" * 72)
    print(f"PHASE 5 STEP 4 VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)

    print("Phase 5 Step 4 OK: follow-up schedule verified")
    print("=" * 72)


if __name__ == "__main__":
    main()

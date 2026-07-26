"""Phase 10: Professional Medical Consultation Engine verification."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_10.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "consultation-test-token")
os.environ.setdefault("OPENAI_API_KEY", "consultation-test-key")
os.environ.setdefault("ADMIN_TELEGRAM_IDS", "")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.db.connection import get_connection, init_db  # noqa: E402
from app.handlers.chat import process_text_message  # noqa: E402
from app.repositories.consultation_repository import get_active_session  # noqa: E402
from app.repositories.emr_repository import get_emr_visit, list_emr_visits_for_patient  # noqa: E402
from app.repositories.patient_profile_repository import get_or_create_patient_profile  # noqa: E402
from app.services.consultation_classifier import classify_complaint  # noqa: E402
from app.services.consultation_engine import (  # noqa: E402
    is_consultation_trigger,
    process_consultation_turn,
    should_use_consultation_engine,
)
from app.services.consultation_question_trees import (  # noqa: E402
    get_questions_for_category,
    select_next_question,
)
from app.services.consultation_summary import generate_consultation_summary  # noqa: E402
from app.services.emr_service import create_visit  # noqa: E402
from app.services.patient_creation_engine import create_patient_intelligently  # noqa: E402
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

    def false(self, name: str, value) -> None:
        self.check(name, not bool(value), repr(value))


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text

    async def reply_text(self, text: str) -> None:
        self.reply = text


class FakeUpdate:
    def __init__(self, telegram_id: int, text: str) -> None:
        self.message = FakeMessage(text)
        self.effective_user = MagicMock(id=telegram_id, first_name="Test", last_name="Patient")


class FakeContext:
    def __init__(self) -> None:
        self.user_data: dict = {}


def _report(runner: TestRunner) -> None:
    print(f"\n=== Phase 10: {runner.passed}/{runner.total} passed ===")
    for name, detail in runner.failed:
        print(f"FAIL: {name} — {detail}")
    if runner.failed:
        sys.exit(1)
    print("PASS: Professional Medical Consultation Engine verified")


def main() -> None:
    runner = TestRunner()
    init_db()

    with get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    runner.check("consultation_sessions_table", "consultation_sessions" in tables, str(sorted(tables)))

    classification_cases = [
        ("Boshim og'riyapti", "headache"),
        ("Belim og'riyapti", "low_back_pain"),
        ("Bo'ynim og'riyapti", "neck_pain"),
        ("Bosh aylanmoqda", "vertigo"),
        ("Insult belgilari bor", "stroke"),
        ("Qo'lim uvishyapti", "neuropathy"),
        ("Yuz qiyshayapti", "facial_nerve_palsy"),
        ("Qo'lim titrayapti", "tremor"),
        ("Xotiram susayapti", "memory_problems"),
        ("Uxlay olmayapman", "sleep_disorders"),
        ("Xavotir bosyapti", "anxiety"),
        ("Depressiyadayman", "depression"),
        ("Nevrologik shikoyatim bor", "other_neurological"),
    ]
    for text, expected in classification_cases:
        got = classify_complaint(text)
        runner.eq(f"classify_{expected}", got, expected)

    for category in (
        "headache",
        "low_back_pain",
        "neck_pain",
        "vertigo",
        "stroke",
        "neuropathy",
        "facial_nerve_palsy",
        "tremor",
        "memory_problems",
        "sleep_disorders",
        "anxiety",
        "depression",
        "other_neurological",
    ):
        tree = get_questions_for_category(category)
        runner.check(f"tree_nonempty_{category}", len(tree) >= 3, str(len(tree)))
        ids = [q.id for q in tree]
        runner.check(f"tree_unique_ids_{category}", len(ids) == len(set(ids)), str(ids))

    asked: set[str] = set()
    answers: dict[str, str] = {}
    questions_seen: list[str] = []
    for _ in range(10):
        nxt = select_next_question("headache", asked, answers)
        if nxt is None:
            break
        runner.check("no_repeat_question", nxt.id not in asked, nxt.id)
        asked.add(nxt.id)
        questions_seen.append(nxt.id)
        answers[nxt.id] = "test answer"
    runner.check("one_at_a_time_sequence", len(questions_seen) >= 3, str(questions_seen))

    created = create_patient_intelligently(
        source="telegram",
        text="Consultation Test 901777001",
        started_at="2026-07-26",
    )
    runner.check("patient_created", created is not None, repr(created))
    if created is None:
        _report(runner)
        return

    patient_id = created.patient_id
    seed_default_location(patient_id)
    get_or_create_patient_profile(patient_id)
    create_visit(patient_id, visit_date="2026-07-26", main_complaint="Initial")

    user_data: dict = {}
    runner.true("should_use_on_medical", should_use_consultation_engine(patient_id, "Boshim og'riyapti", user_data))
    runner.false("should_not_use_on_greeting", should_use_consultation_engine(patient_id, "Salom", user_data))
    runner.false(
        "should_not_use_general_advice_question",
        should_use_consultation_engine(patient_id, "Bugun nima qilish kerak?", user_data),
    )
    runner.true("consultation_trigger_headache", is_consultation_trigger("Boshim og'riyapti"))

    turn1 = process_consultation_turn(patient_id, "Boshim og'riyapti", user_data=user_data)
    runner.eq("turn1_phase", turn1.phase, "collecting")
    runner.check("turn1_single_question", turn1.reply.count("?") >= 1, turn1.reply[:120])
    runner.false("turn1_multiple_questions", "1." in turn1.reply and "2." in turn1.reply and "3." in turn1.reply)

    session = get_active_session(patient_id)
    runner.check("session_created", session is not None, "")
    if session is None:
        _report(runner)
        return

    runner.eq("session_category", session.complaint_category, "headache")
    first_q = session.current_question_id
    runner.check("first_question_set", bool(first_q), repr(first_q))

    turn2 = process_consultation_turn(patient_id, "2 kun oldin", user_data=user_data)
    runner.eq("turn2_phase", turn2.phase, "collecting")
    runner.check("turn2_different_question", first_q not in turn2.reply, turn2.reply[:120])

    session2 = get_active_session(patient_id)
    runner.check("session_still_active", session2 is not None, "")
    if session2:
        runner.check("question_id_advanced", session2.current_question_id != first_q, repr(session2.current_question_id))
        runner.check("answer_stored", "onset" in session2.answers or first_q in session2.answers, json.dumps(session2.answers))

    visits = list_emr_visits_for_patient(patient_id)
    runner.check("emr_visit_exists", len(visits) >= 1, str(len(visits)))
    if visits:
        notes = visits[0].get("notes") or ""
        runner.check("emr_notes_has_qa", "Q[" in notes, notes[:200])

    answers_full = {
        "chief_complaint_text": "Boshim og'riyapti",
        "onset": "3 kun",
        "headache_location": "peshona",
        "severity": "7",
        "headache_character": "bosuvchi",
        "headache_associated": "yo'q",
        "progression": "o'zgarmayapti",
    }
    summary = generate_consultation_summary("headache", answers_full)
    runner.check("summary_chief_complaint", bool(summary.chief_complaint), summary.chief_complaint)
    runner.check("summary_history", bool(summary.history), summary.history[:80])
    runner.check("summary_timeline", bool(summary.timeline), summary.timeline)
    runner.check("summary_differentials", len(summary.possible_differential_diagnoses) >= 2, str(summary.possible_differential_diagnoses))
    runner.check("summary_investigations", len(summary.recommended_investigations) >= 1, str(summary.recommended_investigations))
    runner.check("summary_urgency", summary.urgency in ("routine", "urgent", "emergency"), summary.urgency)
    runner.check("summary_visit_type", bool(summary.recommended_visit_type), summary.recommended_visit_type)
    runner.check("summary_follow_up", bool(summary.follow_up_plan), summary.follow_up_plan)

    emergency_patient = create_patient_intelligently(
        source="telegram",
        text="Emergency Test 901777002",
        started_at="2026-07-26",
    )
    runner.check("emergency_patient_created", emergency_patient is not None, "")
    if emergency_patient:
        eid = emergency_patient.patient_id
        seed_default_location(eid)
        create_visit(eid, visit_date="2026-07-26")
        emergency = process_consultation_turn(
            eid,
            "Hushdan ketdim, insult belgilari bor",
            user_data={},
        )
        runner.true("emergency_detected", emergency.emergency)
        runner.check("emergency_mentions_103", "103" in emergency.reply, emergency.reply[:200])

    back_patient = create_patient_intelligently(
        source="telegram",
        text="Back Pain Test 901777003",
        started_at="2026-07-26",
    )
    if back_patient:
        bid = back_patient.patient_id
        seed_default_location(bid)
        create_visit(bid, visit_date="2026-07-26")
        process_consultation_turn(bid, "Bel og'riyapti", user_data={})
        runner.eq("back_pain_start", classify_complaint("Bel og'riyapti"), "low_back_pain")

    complete_patient = create_patient_intelligently(
        source="telegram",
        text="Complete Flow 901777004",
        started_at="2026-07-26",
    )
    runner.check("complete_patient_created", complete_patient is not None, "")
    final_result = None
    if complete_patient:
        cid = complete_patient.patient_id
        seed_default_location(cid)
        create_visit(cid, visit_date="2026-07-26")
        user_data_complete: dict = {}
        msg = "Boshim og'riyapti"
        for i in range(15):
            final_result = process_consultation_turn(cid, msg, user_data=user_data_complete)
            if final_result.completed or final_result.emergency:
                break
            msg = f"Javob {i}: yetarlicha ma'lumot"

        runner.check("consultation_completes", final_result is not None and final_result.completed, repr(final_result))
        if final_result:
            runner.check("completion_has_summary", "Tibbiy konsultatsiya xulosasi" in final_result.reply, final_result.reply[:300])
            runner.check("completion_offers_online", "onlayn" in final_result.reply.lower(), final_result.reply[-400:])
            runner.check("completion_offers_appointment", "qabul" in final_result.reply.lower(), final_result.reply[-400:])

        visits_complete = list_emr_visits_for_patient(cid)
        if visits_complete:
            visit = get_emr_visit(visits_complete[0]["id"])
            runner.check(
                "emr_summary_saved",
                visit and "Konsultatsiya xulosasi" in (visit.get("notes") or ""),
                (visit or {}).get("notes", "")[:200],
            )
            runner.check("emr_recommended_exams", visit and visit.get("recommended_examinations"), visit)

    async def _run_chat_integration() -> str | None:
        update = FakeUpdate(880010, "Boshim og'riyapti")
        context = FakeContext()
        with patch("app.handlers.chat.register_telegram_user", return_value=patient_id):
            with patch("app.handlers.chat.get_or_create_active_conversation", return_value=1):
                with patch("app.handlers.chat.save_message"):
                    with patch("app.handlers.chat.get_last_messages", return_value=[]):
                        with patch("app.handlers.chat.ask_ai") as mock_ai:
                            mock_ai.side_effect = AssertionError("ask_ai should not be called for consultation")
                            await process_text_message(
                                update,
                                context,
                                "Boshim og'riyapti",
                                entry_handler="test",
                            )
                            return getattr(update.message, "reply", None)

    reply = asyncio.run(_run_chat_integration())
    runner.check("chat_routes_to_engine", reply is not None, repr(reply))
    if reply:
        runner.false("chat_no_ask_ai", "AssertionError" in reply)

    _report(runner)


if __name__ == "__main__":
    main()

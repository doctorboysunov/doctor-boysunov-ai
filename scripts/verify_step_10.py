"""Phase 10: AI Neurology Assistant verification (GPT-driven, not scripted)."""

from __future__ import annotations

import asyncio
import json
import os
import re
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
os.environ["ADMIN_TELEGRAM_IDS"] = ""

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.db.connection import get_connection, init_db  # noqa: E402
from app.handlers.chat import process_text_message  # noqa: E402
from app.repositories.consultation_repository import get_active_session, get_session_by_id  # noqa: E402
from app.repositories.emr_repository import get_emr_visit, list_emr_visits_for_patient  # noqa: E402
from app.services.consultation_ai import (  # noqa: E402
    HELP_MENU_QUESTION,
    LEGAL_DISCLAIMER,
    ConversationIntentAnalysis,
    DoctorEmrUpdate,
    InternalReasoning,
    NeurologyTurnOutput,
    _limit_sentences,
    build_help_menu_reply,
    parse_help_choice,
)
from app.services.consultation_classifier import classify_complaint  # noqa: E402
from app.services.consultation_engine import (  # noqa: E402
    is_consultation_trigger,
    process_consultation_turn,
    should_use_consultation_engine,
)
from app.services.consultation_red_flags import build_consultation_emergency_response  # noqa: E402
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


def _sentence_count(text: str) -> int:
    parts = re.split(r"[.!?]+", text)
    return len([part for part in parts if part.strip()])


def _mock_intent_continue(**kwargs) -> ConversationIntentAnalysis:
    return ConversationIntentAnalysis(
        is_answering_previous_question=True,
        confidence="high",
        recommended_action="continue_session",
    )


def _mock_gpt_collecting(question: str, *, topics: list[str] | None = None) -> NeurologyTurnOutput:
    internal = InternalReasoning(
        what_i_know=["Bosh og'rig'i"],
        missing_information=["Boshlanish vaqti"],
        emergency_assessment="none",
        possible_neurological_causes=["Migren"],
        next_question_topic="onset",
        next_question_rationale="Anamnez uchun muhim",
    )
    return NeurologyTurnOutput(
        patient_reply=question,
        ready_for_help_menu=False,
        known_facts={"last_question": question},
        topics_covered=topics or ["onset"],
        doctor_emr=DoctorEmrUpdate(
            chief_complaint="Bosh og'rig'i",
            history="Bemor shikoyat bildirdi",
            clinical_notes="Telegram konsultatsiya",
        ),
        internal_reasoning=internal,
        session_summary={
            "clinical_brain": {
                "step1_patient_meaning": "Bosh og'rig'i",
                "step3_hypotheses": [{"name": "Migren", "probability": "medium", "rationale": ""}],
                "step4_emergency_assessment": "none",
            },
            "doctor_emr": DoctorEmrUpdate(
                chief_complaint="Bosh og'rig'i",
                history="Bemor shikoyat bildirdi",
                clinical_notes="Telegram konsultatsiya",
            ).to_dict(),
            "internal_reasoning": internal.to_dict(),
        },
    )


def _mock_gpt_ready(summary: str = "Bosh og'rig'i 3 kundan beri.") -> NeurologyTurnOutput:
    internal = InternalReasoning(
        what_i_know=["Bosh og'rig'i", "3 kun"],
        possible_neurological_causes=["Migren", "Tension headache"],
        emergency_assessment="none",
    )
    doctor = DoctorEmrUpdate(
        chief_complaint="Bosh og'rig'i",
        history="3 kun",
        differential_diagnoses=["Migren", "Tension headache"],
        recommended_investigations=["Qon bosimi"],
    )
    return NeurologyTurnOutput(
        patient_reply="",
        ready_for_help_menu=True,
        brief_summary_for_patient=summary,
        topics_covered=["onset", "location", "severity"],
        doctor_emr=doctor,
        internal_reasoning=internal,
        session_summary={
            "clinical_brain": {
                "step1_patient_meaning": "Bosh og'rig'i 3 kun",
                "step3_hypotheses": [{"name": "Migren", "probability": "high", "rationale": ""}],
                "step7_ready_for_summary": True,
            },
            "doctor_emr": doctor.to_dict(),
            "internal_reasoning": internal.to_dict(),
        },
    )


class FakeUser:
    def __init__(self, telegram_id: int) -> None:
        self.id = telegram_id
        self.username = "patient"
        self.full_name = "Patient Test"


class FakeMessage:
    def __init__(self, text: str, user: FakeUser) -> None:
        self.text = text
        self.from_user = user
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, telegram_id: int, text: str) -> None:
        user = FakeUser(telegram_id)
        self.effective_user = user
        self.message = FakeMessage(text, user)


class FakeContext:
    def __init__(self) -> None:
        self.user_data: dict = {}


def _report(runner: TestRunner) -> None:
    print(f"\n=== Phase 10 AI Neurology: {runner.passed}/{runner.total} passed ===")
    for name, detail in runner.failed:
        print(f"FAIL: {name} — {detail}")
    if runner.failed:
        sys.exit(1)
    print("PASS: AI Neurology Assistant verified")


def main() -> None:
    runner = TestRunner()
    init_db()

    runner.check("short_reply_limit", _sentence_count(_limit_sentences("A. B. C. D. E.")) <= 4, "")
    runner.eq("parse_online", parse_help_choice("Onlayn konsultatsiya"), "online")
    runner.eq("parse_clinic", parse_help_choice("Klinikada qabul"), "clinic")
    runner.eq("parse_continue", parse_help_choice("Savollarni davom ettirish"), "continue")
    menu = build_help_menu_reply("Bosh og'rig'i 3 kundan beri.")
    runner.check("help_menu_understood", "Men sizning holatingizni tushundim" in menu, menu)
    runner.check("help_menu_one_question", menu.count(HELP_MENU_QUESTION) == 1, menu)
    runner.check("help_menu_options_order", menu.index("Savollarni davom ettirish") < menu.index("Onlayn konsultatsiya"), menu)
    runner.check("help_menu_options", "Onlayn konsultatsiya" in menu and "Savollarni davom ettirish" in menu, menu)

    emergency = build_consultation_emergency_response(["stroke"])
    runner.check("emergency_fixed_script", "103" in emergency, emergency[:80])

    runner.eq("classify_headache", classify_complaint("Boshim og'riyapti"), "headache")
    runner.true("consultation_trigger", is_consultation_trigger("Boshim og'riyapti"))

    created = create_patient_intelligently(
        source="telegram",
        text="AI Neuro Test 901888001",
        started_at="2026-07-26",
    )
    runner.check("patient_created", created is not None, "")
    if not created:
        _report(runner)
        return

    patient_id = created.patient_id
    seed_default_location(patient_id)
    create_visit(patient_id, visit_date="2026-07-26")
    user_data: dict = {}

    gpt_calls: list[dict] = []

    def track_gpt(**kwargs):
        gpt_calls.append(kwargs)
        if len(gpt_calls) == 1:
            return _mock_gpt_collecting("Tushundim. Qachondan beri og'riyapti?", topics=["opening_complaint"])
        if len(gpt_calls) == 2:
            return _mock_gpt_collecting("Qayeri og'riyapti — peshona yoki chakka?", topics=["onset"])
        return _mock_gpt_ready()

    with patch("app.services.consultation_engine.run_neurology_turn", side_effect=track_gpt):
        with patch("app.services.consultation_engine.run_conversation_intent_analysis", side_effect=_mock_intent_continue):
            turn1 = process_consultation_turn(patient_id, "Boshim og'riyapti", user_data=user_data)
            turn2 = process_consultation_turn(patient_id, "3 kun oldin", user_data=user_data)
            turn3 = process_consultation_turn(patient_id, "Peshonada", user_data=user_data)

    runner.check("gpt_called_each_turn", len(gpt_calls) >= 3, str(len(gpt_calls)))
    runner.check("turn1_short", _sentence_count(turn1.reply.split(LEGAL_DISCLAIMER)[0]) <= 4, turn1.reply[:120])
    runner.check("turn1_disclaimer", LEGAL_DISCLAIMER in turn1.reply, turn1.reply[-80:])
    runner.check("turn1_no_script_intro", "konsultatsiya boshlaymiz" not in turn1.reply.lower(), turn1.reply)
    runner.eq("turn3_phase", turn3.phase, "awaiting_help_choice")
    runner.check("turn3_understood", "Men sizning holatingizni tushundim" in turn3.reply, turn3.reply)
    runner.check("turn3_not_immediate_online", "onlayn yozilish" not in turn3.reply.lower(), turn3.reply)

    session = get_active_session(patient_id)
    runner.check("session_awaiting_help", session is not None and session.phase == "awaiting_help_choice", repr(session))

    visits = list_emr_visits_for_patient(patient_id)
    if visits:
        notes = get_emr_visit(visits[0]["id"]).get("notes") or ""
        runner.check("doctor_emr_saved", "Shifokor EMR" in notes, notes[:200])
        runner.check("reasoning_in_emr", "Clinical Brain" in notes or "AI klinik mulohaza" in notes, notes[:200])
        runner.check("patient_reply_not_in_emr_only", HELP_MENU_QUESTION not in notes, notes[:200])

    with patch("app.services.consultation_engine.run_neurology_turn", return_value=_mock_gpt_collecting("Yana bir savol")):
        with patch("app.services.consultation_engine.run_conversation_intent_analysis", side_effect=_mock_intent_continue):
            turn4 = process_consultation_turn(patient_id, "Savollarni davom ettirish", user_data=user_data)
    runner.eq("continue_choice_phase", turn4.phase, "collecting")

    session_after = get_active_session(patient_id)
    runner.check("resume_collecting", session_after is not None and session_after.phase == "collecting", "")

    patient2 = create_patient_intelligently(
        source="telegram", text="AI Neuro Test 901888002", started_at="2026-07-26"
    )
    if patient2:
        pid2 = patient2.patient_id
        seed_default_location(pid2)
        create_visit(pid2, visit_date="2026-07-26")
        ud2: dict = {}

        def gpt_flow(**kwargs):
            if len(gpt_flow.calls) == 0:
                gpt_flow.calls.append(1)
                return _mock_gpt_collecting("Qachondan beri?")
            return _mock_gpt_ready()

        gpt_flow.calls = []

        with patch("app.services.consultation_engine.run_neurology_turn", side_effect=gpt_flow):
            with patch("app.services.consultation_engine.run_conversation_intent_analysis", side_effect=_mock_intent_continue):
                with patch(
                    "app.services.consultation_engine.run_help_followup_turn",
                    return_value="Onlayn konsultatsiya uchun mutaxassisimiz tez orada bog'lanadi.",
                ):
                    process_consultation_turn(pid2, "Belim og'riyapti", user_data=ud2)
                    process_consultation_turn(pid2, "1 hafta", user_data=ud2)
                    online_turn = process_consultation_turn(pid2, "Onlayn konsultatsiya", user_data=ud2)
        runner.eq("online_choice_keeps_session", online_turn.phase, "collecting")
        runner.check("online_session_active", get_active_session(pid2) is not None, repr(get_active_session(pid2)))
        runner.check("online_reply_short", _sentence_count(online_turn.reply) <= 4, online_turn.reply)

    async def _chat_integration() -> str | None:
        update = FakeUpdate(880020, "Boshim og'riyapti")
        context = FakeContext()
        with patch("app.handlers.chat.register_telegram_user", return_value=patient_id):
            with patch("app.handlers.chat.get_or_create_active_conversation", return_value=1):
                with patch("app.handlers.chat.save_message"):
                    with patch("app.handlers.chat.ask_ai") as mock_ai:
                        mock_ai.side_effect = AssertionError("ask_ai must not run")
                        with patch(
                            "app.services.consultation_engine.run_neurology_turn",
                            return_value=_mock_gpt_collecting("Qachondan beri og'riyapti?"),
                        ):
                            with patch(
                                "app.services.consultation_engine.run_conversation_intent_analysis",
                                side_effect=_mock_intent_continue,
                            ):
                                await process_text_message(
                                update, context, "Boshim og'riyapti", entry_handler="test"
                            )
                            if update.message.reply_text.await_args:
                                return update.message.reply_text.await_args.args[0]
        return None

    chat_reply = asyncio.run(_chat_integration())
    runner.check("chat_uses_gpt_engine", chat_reply is not None, repr(chat_reply))
    runner.check("chat_no_script_tree", chat_reply is None or "konsultatsiya boshlaymiz" not in (chat_reply or "").lower(), chat_reply)

    runner.check("topics_not_empty_after_turns", len(gpt_calls) >= 3, json.dumps(gpt_calls, default=str)[:200])

    _report(runner)


if __name__ == "__main__":
    main()

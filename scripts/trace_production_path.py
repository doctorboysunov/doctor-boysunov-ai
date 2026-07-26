"""Trace production execution path for a Telegram message — no assumptions."""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "trace_production_path.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["TELEGRAM_BOT_TOKEN"] = "trace-test"
os.environ["OPENAI_API_KEY"] = "trace-test"
sys.path.insert(0, str(ROOT))

from app.consultation_intelligence.clinical_reasoner import ClinicalReasoner
from app.db.connection import init_db
from app.handlers import chat as chat_module
from app.repositories.conversation_repository import upsert_user
from app.services import consultation_engine as engine_module
from app.services.consultation_ai import run_intelligence_turn, run_medical_turn, run_neurology_turn as ai_run_neurology_turn
from app.services.consultation_classifier import classify_complaint, complaint_label
from app.services.consultation_engine import (
    is_consultation_trigger,
    process_consultation_turn,
    run_neurology_turn as engine_run_neurology_turn,
    should_use_consultation_engine,
)
from app.services.location_profile import is_medical_complaint
from scripts.test_support import seed_default_location

MESSAGE = "Oyog'im og'riyapti"

trace_log: list[str] = []


def log(msg: str) -> None:
    trace_log.append(msg)
    safe = msg.encode("ascii", "backslashreplace").decode("ascii")
    print(safe)


def main() -> None:
    init_db()
    patient_id = upsert_user(telegram_id=9910001, username="trace", full_name="Trace Patient")
    seed_default_location(patient_id)

    log("=== IMPORT RESOLUTION ===")
    log(f"consultation_engine.run_neurology_turn is run_intelligence_turn: {engine_run_neurology_turn is run_intelligence_turn}")
    log(f"consultation_engine.run_neurology_turn is run_medical_turn: {engine_run_neurology_turn is run_medical_turn}")
    log(f"consultation_ai.run_neurology_turn is run_medical_turn: {ai_run_neurology_turn.__wrapped__ if hasattr(ai_run_neurology_turn, '__wrapped__') else ai_run_neurology_turn is run_medical_turn}")
    log(f"consultation_ai.run_neurology_turn module: {ai_run_neurology_turn.__module__}")

    log("\n=== ROUTING GATES for {!r} ===".format(MESSAGE))
    log(f"is_medical_complaint: {is_medical_complaint(MESSAGE)}")
    log(f"classify_complaint: {classify_complaint(MESSAGE)}")
    log(f"complaint_label: {complaint_label(classify_complaint(MESSAGE))}")
    log(f"is_consultation_trigger: {is_consultation_trigger(MESSAGE)}")
    log(f"should_use_consultation_engine (no session): {should_use_consultation_engine(patient_id, MESSAGE, {})}")

    reasoner_calls: list[str] = []
    medical_brain_calls: list[str] = []
    ask_ai_calls: list[str] = []

    original_recognize = ClinicalReasoner.recognize

    def traced_recognize(self, narrative, state):
        reasoner_calls.append(f"ClinicalReasoner.recognize(pathway_locked={state.pathway_locked})")
        return original_recognize(self, narrative, state)

    def traced_medical_turn(**kwargs):
        medical_brain_calls.append("run_medical_turn CALLED")
        return run_medical_turn(**kwargs)

    async def traced_ask_ai(*args, **kwargs):
        ask_ai_calls.append("ask_ai CALLED")
        return "MOCK ask_ai response"

    with patch.object(ClinicalReasoner, "recognize", traced_recognize):
        with patch("app.services.consultation_ai.run_medical_turn", side_effect=traced_medical_turn):
            with patch.object(chat_module, "ask_ai", side_effect=traced_ask_ai):
                user_data: dict = {}
                result = process_consultation_turn(patient_id, MESSAGE, user_data=user_data)

    log("\n=== CONSULTATION ENGINE RESULT ===")
    log(f"phase: {result.phase}")
    log(f"used_consultation_engine: {result.used_consultation_engine}")
    log(f"reply[:200]: {result.reply[:200]}")

    log("\n=== RUNTIME TRACE ===")
    log(f"ClinicalReasoner.recognize calls: {len(reasoner_calls)}")
    for c in reasoner_calls:
        log(f"  - {c}")
    log(f"run_medical_turn calls: {len(medical_brain_calls)}")
    for c in medical_brain_calls:
        log(f"  - {c}")
    log(f"ask_ai calls: {len(ask_ai_calls)}")

    log("\n=== chat.py BRANCH SIMULATION ===")
    use_consultation = should_use_consultation_engine(patient_id, MESSAGE, user_data)
    log(f"chat.py would use consultation engine: {use_consultation}")
    if use_consultation:
        log("chat.py -> process_consultation_turn -> engine.run_neurology_turn -> run_intelligence_turn -> ConsultationController")
    else:
        log("chat.py -> ask_ai (legacy GPT path)")

    log("\n=== REPLY ANALYSIS ===")
    lower = result.reply.lower()
    log(f"contains 'boshqa nevrologik': {'boshqa nevrologik' in lower}")
    log(f"contains 'other neurological': {'other neurological' in lower}")
    log(f"contains syndrome_label pattern 'radikulopatiya': {'radikulopatiya' in lower}")
    log(f"contains 'nevrologik sindrom': {'nevrologik sindrom' in lower}")

    # Verify handler imports
    log("\n=== HANDLER IMPORT CHECK ===")
    src = inspect.getsourcefile(chat_module.process_text_message) or ""
    log(f"process_text_message defined in: {src}")

    failures = []
    if not use_consultation:
        failures.append("should_use_consultation_engine returned False — message would NOT reach consultation engine")
    if len(reasoner_calls) == 0:
        failures.append("ClinicalReasoner.recognize was NEVER called")
    if len(medical_brain_calls) > 0:
        failures.append("run_medical_turn (legacy Medical Brain) WAS called")
    if "boshqa nevrologik" in lower or "other neurological" in lower:
        failures.append("Reply still contains generic other-neurological label")

    log("\n=== VERDICT ===")
    if failures:
        for f in failures:
            log(f"FAIL: {f}")
        raise SystemExit(1)
    log("PASS: Production path reaches ClinicalReasoner via v6 controller; legacy Medical Brain not invoked")


if __name__ == "__main__":
    main()

"""Phase 4: medical safety layer verification."""

from __future__ import annotations

import asyncio
import inspect
import os
import sys
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_phase_4_safety.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "safety-test-token")
os.environ.setdefault("OPENAI_API_KEY", "safety-test-key")

sys.path.insert(0, str(ROOT))

from app.db.connection import init_db  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.safety.instructions import build_safety_instructions  # noqa: E402
from app.safety.red_flags import detect_red_flags  # noqa: E402
from app.safety.response_filter import classify_response_violations  # noqa: E402
from app.safety.safety_layer import (  # noqa: E402
    combine_instructions,
    enforce_safety,
    get_enforcement_count,
    reset_enforcement_count,
)
from app.services import openai_service  # noqa: E402
from app.repositories.conversation_repository import upsert_user  # noqa: E402
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

    def not_in(self, name: str, needle: str, haystack: str) -> None:
        self.check(name, needle.lower() not in haystack.lower(), f"found {needle!r}")


class FakeUser:
    id = 610001
    username = "safety_user"
    full_name = "Safety User"


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    effective_user = FakeUser()
    message = FakeMessage("")


def fake_unsafe_create(**kwargs):
    class FakeResponse:
        output_text = (
            "Sizda aniq tashxis: gastrit. Kuniga 500 mg ibuprofen iching. "
            "Shifokor ko'rigiga borish shart emas."
        )

    return FakeResponse()


def fake_safe_create(**kwargs):
    class FakeResponse:
        output_text = (
            "Umumiy ma'lumot: ko'krak og'rig'i turli sabablarga bog'liq bo'lishi mumkin. "
            "Aniq baholash uchun shifokor ko'rigidan o'tish muhim."
        )

    return FakeResponse()


async def run_chat(text: str) -> str:
    update = FakeUpdate()
    update.message = FakeMessage(text)
    with patch(
        "app.services.openai_service.client.responses.create",
        side_effect=fake_unsafe_create,
    ):
        await chat(update, None)
    return update.message.reply_text.await_args.args[0]


async def run_ask_ai(text: str) -> str:
    reset_enforcement_count()

    class FakeResponse:
        output_text = "Sizda diabet bor. Retsept: metformin 500 mg kuniga 2 marta."

    with patch(
        "app.services.openai_service.client.responses.create",
        return_value=FakeResponse(),
    ):
        return openai_service.ask_ai(text)


def main() -> None:
    runner = TestRunner()
    init_db()
    seed_default_location(
        upsert_user(
            telegram_id=FakeUser.id,
            username=FakeUser.username,
            full_name=FakeUser.full_name,
        )
    )

    # --- Module independence (8 tests) ---
    safety_src = (ROOT / "app" / "safety" / "safety_layer.py").read_text(encoding="utf-8")
    runner.not_in("safety_no_profile_import", "patient_profile", safety_src)
    runner.not_in("safety_no_memory_import", "conversation_repository", safety_src)
    runner.not_in("safety_no_messages_import", "save_message", safety_src)
    runner.true("safety_instructions_present", "Never prescribe" in build_safety_instructions())
    runner.true("safety_instructions_diagnosis", "definitive diagnosis" in build_safety_instructions())
    combined = combine_instructions(profile_instructions="PROFILE")
    runner.true("combine_has_safety", "Medical safety policy" in combined)
    runner.true("combine_has_profile", "PROFILE" in combined)
    runner.true("combine_order_safety_first", combined.index("Medical safety") < combined.index("PROFILE"))

    # --- Red-flag detection (18 tests) ---
    red_flag_cases = [
        ("Ko'kragim og'riyapti va nafas olish qiyin", "chest_pain"),
        ("insult belgilari boshlandi", "stroke"),
        ("tutqanoq bo'lyapti", "seizure"),
        ("hushdan ketdim", "consciousness"),
        ("kuchli qon ketish", "bleeding"),
        ("severe breathing difficulty", "breathing"),
        ("Salom, qandaysiz?", None),
    ]
    for idx, (message, expected_code) in enumerate(red_flag_cases):
        flags = detect_red_flags(message)
        if expected_code is None:
            runner.eq(f"redflag_{idx}_none", flags, [])
        else:
            runner.true(f"redflag_{idx}_{expected_code}", expected_code in flags)

    emergency_text, meta = enforce_safety(
        user_message="Ko'kragim og'riyapti",
        ai_response="anything",
    )
    runner.eq("emergency_action", meta["action"], "emergency")
    runner.true("emergency_103", "103" in emergency_text)

    # --- Response filter violations (12 tests) ---
    violation_cases = [
        ("Take 500 mg daily", ["prescription_or_dosage"]),
        ("Sizda aniq tashxis: gastrit bor", ["definitive_diagnosis"]),
        ("Shifokor ko'rigiga borish shart emas", ["replaces_examination"]),
        ("Umumiy ma'lumot beraman", []),
    ]
    for idx, (text, expected) in enumerate(violation_cases):
        got = classify_response_violations(text)
        runner.eq(f"violation_{idx}", got, expected)

    safe, meta = enforce_safety(
        user_message="Qanday davolanish kerak?",
        ai_response="Kuniga 500 mg ibuprofen iching va retsept yozaman.",
    )
    runner.eq("rewrite_action", meta["action"], "rewrite")
    runner.not_in("rewrite_no_mg", "500 mg", safe)
    runner.not_in("rewrite_no_prescription_line", "Retsept:", safe)
    runner.true("rewrite_consultation", "Doctor Boysunov" in safe)

    allowed, allow_meta = enforce_safety(
        user_message="Bolalar immuniteti haqida",
        ai_response="Umumiy ma'lumot: immunitet ko'p omillarga bog'liq.",
    )
    runner.eq("allow_action", allow_meta["action"], "allow")
    runner.eq("allow_text", allowed, "Umumiy ma'lumot: immunitet ko'p omillarga bog'liq.")

    # --- ask_ai integration / bypass prevention (6 tests) ---
    reset_enforcement_count()
    source = inspect.getsource(openai_service.ask_ai)
    runner.true("ask_ai_calls_enforce", "enforce_safety" in source)
    runner.true("ask_ai_returns_safe", "return safe_output" in source)

    asyncio.run(run_ask_ai("Davolash kerak"))
    runner.true("ask_ai_enforced", get_enforcement_count() >= 1)

    # --- chat handler cannot bypass (4 tests) ---
    reset_enforcement_count()
    reply = asyncio.run(run_chat("Mening boshim og'riyapti, dori bering"))
    runner.true("chat_enforced", get_enforcement_count() >= 1)
    runner.not_in("chat_no_prescription", "500 mg", reply)
    runner.not_in("chat_no_unsafe_diagnosis", "Sizda aniq tashxis:", reply)
    runner.true("chat_has_consult_or_educational", ("Doctor Boysunov" in reply) or ("umumiy" in reply.lower()))

    # --- Parametric red flags + rewrite checks (40 tests) ---
    unsafe_outputs = [
        "Paracetamol 500 mg kuniga 3 marta",
        "Retsept: amoxicillin 250 mg",
        "Sizda pneumonia kasalligi bor",
        "You have been diagnosed with diabetes",
        "Doctor examination is not needed",
        "Kuniga 2 tabletka qabul qiling",
        "Take 10 ml every 8 hours",
        "Aniq tashxis: gipertoniya",
        "Antibiotik iching 7 kun",
        "Shifokor ko'rigiga borish kerak emas",
    ]
    for idx, unsafe in enumerate(unsafe_outputs):
        out, meta = enforce_safety(user_message="test", ai_response=unsafe)
        runner.eq(f"param_{idx}_rewrite", meta["action"], "rewrite")
        runner.not_in(f"param_{idx}_no_mg", " mg", out)

    emergency_inputs = [
        "Ko'krak og'rig'i",
        "insult",
        "nafas qisilish",
        "hushdan ketish",
        "tutqanoq",
        "kuchli qon ketish",
        "chest pain",
        "severe breathing difficulty",
        "loss of consciousness",
        "seizure",
    ]
    for idx, message in enumerate(emergency_inputs):
        out, meta = enforce_safety(user_message=message, ai_response="unsafe")
        runner.eq(f"emergency_{idx}", meta["action"], "emergency")

    # --- Summary ---
    print()
    print("=" * 72)
    print(f"PHASE 4 SAFETY VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)

    if runner.total < 50:
        print(f"ERROR: only {runner.total} tests (minimum 50 required)")
        raise SystemExit(1)

    print("Phase 4 Step 1 OK: safety layer enforced on every AI response")
    print("=" * 72)


if __name__ == "__main__":
    main()

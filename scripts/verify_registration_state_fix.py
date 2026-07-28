"""Verify registration auto-complete and medical pause/resume."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_registration_state_fix.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "reg-state-test")
os.environ.setdefault("OPENAI_API_KEY", "reg-state-test")
os.environ["ADMIN_TELEGRAM_IDS"] = ""

sys.path.insert(0, str(ROOT))

from app.settings import get_settings  # noqa: E402

get_settings.cache_clear()
import app.config  # noqa: E402

importlib.reload(app.config)

from app.db.connection import get_connection, init_db  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.repositories.conversation_repository import upsert_user  # noqa: E402
from app.repositories.patient_profile_repository import get_patient_profile  # noqa: E402
from app.services.location_profile import has_location_stored  # noqa: E402
from app.services.consultation_ai import DoctorEmrUpdate, NeurologyTurnOutput  # noqa: E402
from app.services.registration_state import (  # noqa: E402
    PENDING_REGISTRATION_STEP_KEY,
    REGISTRATION_STATE_KEY,
    registration_snapshot,
)

_MOCK_GPT = NeurologyTurnOutput(
    patient_reply="Tushundim. Qachondan beri og'riyapti?",
    doctor_emr=DoctorEmrUpdate(chief_complaint="Bosh og'rig'i"),
)


class FakeUser:
    def __init__(self, telegram_id: int, username: str, full_name: str):
        self.id = telegram_id
        self.username = username
        self.full_name = full_name


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, user: FakeUser, text: str):
        self.effective_user = user
        self.message = FakeMessage(text)
        self.message.from_user = user


class FakeContext:
    def __init__(self) -> None:
        self.user_data: dict = {}


def profile_row(user_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT country, region, district, address, latitude, longitude "
            "FROM patient_profiles WHERE user_id=?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else {}


async def send(user: FakeUser, text: str, context: FakeContext) -> str:
    update = FakeUpdate(user, text)
    await chat(update, context)
    return update.message.reply_text.await_args.args[0]


async def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    init_db()
    ask_ai = MagicMock(return_value="Medical javob")

    stuck_user = FakeUser(880001, "stuck_patient", "Stuck Patient")
    stuck_user_id = upsert_user(
        telegram_id=stuck_user.id,
        username=stuck_user.username,
        full_name=stuck_user.full_name,
    )
    stuck_context = FakeContext()
    stuck_context.user_data[REGISTRATION_STATE_KEY] = "active"
    stuck_context.user_data[PENDING_REGISTRATION_STEP_KEY] = "share_location"

    from app.repositories.patient_profile_repository import update_patient_profile

    update_patient_profile(
        stuck_user_id,
        full_name="Stuck Patient",
        phone_number="+998901112233",
        country="Uzbekistonda",
        region="Surxandaryo",
        district="Jarqorgon",
        city_region="Surxandaryo",
    )

    print("=== BEFORE (stuck at share_location, required fields already in DB) ===")
    print(
        json.dumps(
            {
                "patient_profiles": profile_row(stuck_user_id),
                "has_location_stored": has_location_stored(get_patient_profile(stuck_user_id)),
                "context": registration_snapshot(stuck_context),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    ask_ai.return_value = "Bosh og'riq uchun dam oling va suv iching."
    with patch("app.handlers.chat.ask_ai", ask_ai), patch(
        "app.services.consultation_engine.run_neurology_turn", return_value=_MOCK_GPT
    ):
        unstuck_reply = await send(stuck_user, "Boshim og'riyapti", stuck_context)

    print("\n=== AFTER (auto-finished + Consultation Engine) ===")
    after_stuck = {
        "patient_profiles": profile_row(stuck_user_id),
        "context": registration_snapshot(stuck_context),
        "reply": unstuck_reply,
    }
    print(json.dumps(after_stuck, ensure_ascii=False, indent=2))
    assert after_stuck["context"]["registration_state"] is None
    assert "?" in unstuck_reply or "og'ri" in unstuck_reply.lower()

    fresh_user = FakeUser(880002, "fresh_patient", "Fresh Patient")
    fresh_user_id = upsert_user(
        telegram_id=fresh_user.id,
        username=fresh_user.username,
        full_name=fresh_user.full_name,
    )
    fresh_context = FakeContext()
    ask_ai.reset_mock()

    print("\n=== RUN: fresh registration (name -> phone -> country -> region -> district -> auto complete) ===")
    with patch("app.handlers.chat.ask_ai", ask_ai):
        await send(fresh_user, "Salom", fresh_context)
        await send(fresh_user, "Fresh Patient", fresh_context)
        await send(fresh_user, "+998901234567", fresh_context)
        await send(fresh_user, "O'zbekiston", fresh_context)
        await send(fresh_user, "Surxandaryo", fresh_context)
        r3 = await send(fresh_user, "Jarqorgon", fresh_context)

    after_complete = {
        "patient_profiles": profile_row(fresh_user_id),
        "has_location_stored": has_location_stored(get_patient_profile(fresh_user_id)),
        "context": registration_snapshot(fresh_context),
        "last_reply": r3,
    }
    print(json.dumps(after_complete, ensure_ascii=False, indent=2))
    assert "saqlandi" in r3.lower(), f"expected auto-complete message, got {r3!r}"
    assert after_complete["context"]["registration_state"] is None
    assert ask_ai.call_count == 0

    pause_user = FakeUser(880003, "pause_patient", "Pause Patient")
    pause_user_id = upsert_user(
        telegram_id=pause_user.id,
        username=pause_user.username,
        full_name=pause_user.full_name,
    )
    pause_context = FakeContext()
    ask_ai.reset_mock()
    ask_ai.return_value = "Bosh og'riq uchun dam oling."

    print("\n=== RUN: medical complaint during registration (pause + AI) ===")
    with patch("app.handlers.chat.ask_ai", ask_ai), patch(
        "app.services.consultation_engine.run_neurology_turn", return_value=_MOCK_GPT
    ):
        await send(pause_user, "Salom", pause_context)
        await send(pause_user, "Pause Patient", pause_context)
        await send(pause_user, "+998907776655", pause_context)
        await send(pause_user, "O'zbekiston", pause_context)
        await send(pause_user, "Surxandaryo", pause_context)
        medical_reply = await send(pause_user, "Boshim og'riyapti", pause_context)

    paused = registration_snapshot(pause_context)
    print(json.dumps({"context": paused, "medical_reply": medical_reply}, ensure_ascii=False, indent=2))
    assert paused["registration_state"] == "paused"
    assert paused["pending_registration_step"] == "district"
    assert "?" in medical_reply or "og'ri" in medical_reply.lower()

    print("\n=== RUN: resume registration after medical pause ===")
    with patch("app.handlers.chat.ask_ai", ask_ai):
        resume_reply = await send(pause_user, "Jarqorgon", pause_context)

    after_resume = {
        "patient_profiles": profile_row(pause_user_id),
        "context": registration_snapshot(pause_context),
        "resume_reply": resume_reply,
    }
    print(json.dumps(after_resume, ensure_ascii=False, indent=2))
    assert "saqlandi" in resume_reply.lower()
    assert after_resume["context"]["registration_state"] is None

    print("\nPASS: registration state machine fix verified")


if __name__ == "__main__":
    asyncio.run(main())

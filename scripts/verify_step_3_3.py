"""Step 3.3: expanded patient profile fields and automatic extraction."""

import asyncio
import json
import os
import sys
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "test_step_3_3.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "verify-token")
os.environ.setdefault("OPENAI_API_KEY", "verify-key")

sys.path.insert(0, str(ROOT))

from app.db.connection import get_connection, init_db  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.repositories.patient_profile_repository import get_patient_profile  # noqa: E402
from app.services.patient_context import build_profile_instructions  # noqa: E402
from app.services.profile_extraction import extract_profile_updates  # noqa: E402
from app.settings import get_settings  # noqa: E402

openai_requests: list[dict] = []


class FakeUser:
    id = 770001
    username = "expanded_profile"
    full_name = "Expanded Profile"


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, text: str):
        self.effective_user = FakeUser()
        self.message = FakeMessage(text)


def fake_responses_create(**kwargs):
    openai_requests.append(kwargs)

    class FakeResponse:
        output_text = "OK"
        id = f"resp_{len(openai_requests)}"

    return FakeResponse()


def assert_extraction(message: str, expected: dict) -> None:
    got = extract_profile_updates(message)
    for key, value in expected.items():
        assert got.get(key) == value, f"message={message!r} expected {key}={value!r} got {got!r}"


async def run_turn(text: str) -> str:
    out = StringIO()
    with redirect_stdout(out):
        with patch(
            "app.services.openai_service.client.responses.create",
            side_effect=fake_responses_create,
        ):
            await chat(FakeUpdate(text), None)
    return out.getvalue()


async def main() -> None:
    init_db()

    assert_extraction("Men 32 yoshdaman.", {"age": 32})
    assert_extraction("Men ayolman.", {"sex": "female"})
    assert_extraction("Bo'yim 165 sm.", {"height_cm": 165})
    assert_extraction("Vaznim 62 kg.", {"weight_kg": 62})
    assert_extraction("Telefon raqamim +998901112233.", {"phone_number": "+998901112233"})
    assert_extraction(
        "Manzilim Toshkent shahar, Yunusobod 12-uy.",
        {"address": "Toshkent shahar, Yunusobod 12-uy"},
    )
    assert_extraction("Kasbim hamshira.", {"occupation": "hamshira"})
    assert_extraction("Allergiyam penitsillinga.", {"allergies": "penitsillinga"})
    assert_extraction("Menda diabet bor.", {"chronic_diseases": "diabet"})
    assert_extraction(
        "Favqulodda kontakt: Onam Malika +998909998877.",
        {"emergency_contact": "Onam Malika +998909998877"},
    )

    await run_turn("Mening ismim Dilnoza.")
    await run_turn("Men 32 yoshdaman.")
    await run_turn("Bo'yim 165 sm.")
    await run_turn("Vaznim 62 kg.")
    await run_turn("Allergiyam penitsillinga.")

    profile = get_patient_profile(1)
    assert profile is not None
    assert profile["full_name"] == "Dilnoza"
    assert profile["age"] == 32
    assert profile["height_cm"] == 165
    assert profile["weight_kg"] == 62
    assert profile["allergies"] == "penitsillinga"

    await run_turn("Menda yong'oqka allergiyam bor.")
    profile = get_patient_profile(1)
    assert "penitsillin" in profile["allergies"].lower()
    assert "yong'oq" in profile["allergies"].lower()

    instructions = build_profile_instructions(profile)
    assert instructions is not None
    assert "Do not ask the patient to repeat information" in instructions
    assert "height_cm: 165" in instructions
    assert "weight_kg: 62" in instructions
    assert "allergies:" in instructions

    last_request = openai_requests[-1]
    assert "instructions" in last_request
    assert "Dilnoza" in last_request["instructions"]
    assert "yong'oq" in last_request["instructions"]

    with get_connection() as conn:
        message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert message_count > 0

    get_settings.cache_clear()
    init_db()

    await run_turn("Surunkali kasalligim gipertoniya.")
    profile_after_restart = get_patient_profile(1)
    assert profile_after_restart["full_name"] == "Dilnoza"
    assert profile_after_restart["height_cm"] == 165
    assert "gipertoniya" in profile_after_restart["chronic_diseases"].lower()

    print("Step 3.3 OK: expanded profile fields, merge, AI instructions, restart persistence")


if __name__ == "__main__":
    asyncio.run(main())

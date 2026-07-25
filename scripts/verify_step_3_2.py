"""Step 3.2: inject patient profile into AI requests and auto-update from messages."""

import asyncio
import json
import os
import sys
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "test_step_3_2.db"

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
    id = 660001
    username = "phase3_user"
    full_name = "Phase Three"


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
            update = FakeUpdate(text)
            await chat(update, None)
    return out.getvalue()


async def main() -> None:
    init_db()

    assert_extraction("Mening ismim Sohibnazar.", {"full_name": "Sohibnazar"})
    assert_extraction("Men 32 yoshdaman.", {"age": 32})
    assert_extraction("Men Surxondaryodanman.", {"city_region": "Surxondaryo"})
    assert_extraction("Kasbim dasturchi.", {"occupation": "dasturchi"})
    assert extract_profile_updates("Salom") == {}
    assert extract_profile_updates("Mening ismim kim?") == {}

    await run_turn("Mening ismim Sohibnazar.")
    profile = get_patient_profile(1)
    assert profile is not None
    assert profile["full_name"] == "Sohibnazar"
    assert profile["city_region"] is None

    with get_connection() as conn:
        message_rows = conn.execute(
            "SELECT role, content FROM messages ORDER BY id"
        ).fetchall()
    assert len(message_rows) == 2
    assert message_rows[0]["content"] == "Mening ismim Sohibnazar."
    assert message_rows[0]["role"] == "user"

    first_request = openai_requests[0]
    first_instructions = first_request.get("instructions") or ""
    assert "Sohibnazar" in first_instructions, (
        "AI must read profile on first turn after name is provided"
    )

    await run_turn("Men Surxondaryodanman.")
    profile = get_patient_profile(1)
    assert profile["full_name"] == "Sohibnazar"
    assert profile["city_region"] == "Surxondaryo"

    second_request = openai_requests[1]
    instructions = second_request.get("instructions", "")
    assert instructions, "AI request must include patient profile instructions"
    assert "Sohibnazar" in instructions
    assert "Surxondaryo" in instructions
    assert "Permanent patient profile" in instructions

    history_input = second_request["input"]
    history_serialized = json.dumps(history_input, ensure_ascii=False)
    assert "Surxondaryodanman" in history_serialized
    assert "full_name:" not in history_serialized

    print("Simulating bot restart...")
    get_settings.cache_clear()
    init_db()

    await run_turn("Men 32 yoshdaman.")
    profile_after_restart = get_patient_profile(1)
    assert profile_after_restart["full_name"] == "Sohibnazar"
    assert profile_after_restart["city_region"] == "Surxondaryo"
    assert profile_after_restart["age"] == 32

    third_request = openai_requests[2]
    instructions = third_request["instructions"]
    assert "32" in instructions
    assert "Sohibnazar" in instructions
    assert "Surxondaryo" in instructions

    empty_instructions = build_profile_instructions(
        {
            "full_name": None,
            "age": None,
            "sex": None,
            "phone_number": None,
            "city_region": None,
            "occupation": None,
        }
    )
    assert empty_instructions is None

    print("Step 3.2 OK: profile auto-update, AI instructions, restart persistence")


if __name__ == "__main__":
    asyncio.run(main())

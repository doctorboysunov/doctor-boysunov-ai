"""Phase 5 Step 2: patient address and location verification."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_5_2.db"
LEGACY_DB = ROOT / "data" / "verify_step_5_2_legacy.db"

for db_path in (TEST_DB, LEGACY_DB):
    if db_path.exists():
        db_path.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "location-test-token")
os.environ.setdefault("OPENAI_API_KEY", "location-test-key")

sys.path.insert(0, str(ROOT))

from app.db.connection import get_connection, init_db  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.handlers.location import (  # noqa: E402
    LOCATION_STATE_KEY,
    SHARE_LOCATION_BUTTON,
    build_share_location_keyboard,
    handle_location_share,
    start_location_registration,
)
from app.handlers.start import start  # noqa: E402
from app.repositories.conversation_repository import upsert_user  # noqa: E402
from app.repositories.patient_profile_repository import (  # noqa: E402
    get_or_create_patient_profile,
    get_patient_profile,
    update_patient_profile,
)
from app.services.location_profile import (  # noqa: E402
    has_location_stored,
    is_location_update_trigger,
)
from app.services.patient_context import build_profile_instructions  # noqa: E402
from app.services.openai_service import ask_ai  # noqa: E402


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

    def in_(self, name: str, needle: str, haystack: str) -> None:
        self.check(name, needle in haystack, f"{needle!r} not in {haystack!r}")


class FakeUser:
    id = 720001
    username = "location_user"
    full_name = "Location User"


class FakeLocation:
    def __init__(self, latitude: float, longitude: float) -> None:
        self.latitude = latitude
        self.longitude = longitude


class FakeMessage:
    def __init__(self, text: str | None = None, location: FakeLocation | None = None):
        self.text = text
        self.location = location
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self) -> None:
        self.effective_user = FakeUser()
        self.message = FakeMessage("")


class FakeContext:
    def __init__(self) -> None:
        self.user_data: dict = {}


async def send_text(text: str, context: FakeContext) -> tuple[str, dict]:
    update = FakeUpdate()
    update.message = FakeMessage(text=text)
    await chat(update, context)
    call = update.message.reply_text.await_args
    reply = call.args[0]
    kwargs = call.kwargs
    return reply, kwargs


async def send_location(
    latitude: float,
    longitude: float,
    context: FakeContext,
) -> str:
    update = FakeUpdate()
    update.message = FakeMessage(location=FakeLocation(latitude, longitude))
    await handle_location_share(update, context)
    return update.message.reply_text.await_args.args[0]


async def run_registration(context: FakeContext) -> list[str]:
    steps = [
        "O'zbekiston",
        "Toshkent",
        "Yunusobod",
        "Amir Temur 12-uy",
        "Skip",
    ]
    replies: list[str] = []
    for step in steps:
        reply, _ = await send_text(step, context)
        replies.append(reply)
    return replies


def seed_location(user_id: int) -> None:
    update_patient_profile(
        user_id,
        country="O'zbekiston",
        region="Toshkent",
        district="Yunusobod",
        city_region="Toshkent",
        address="Test manzil",
        latitude=41.2995,
        longitude=69.2401,
    )


def main() -> None:
    runner = TestRunner()
    init_db()

    with get_connection() as conn:
        columns = {
            row[1]: row[2]
            for row in conn.execute("PRAGMA table_info(patient_profiles)").fetchall()
        }

    for column in ("country", "region", "district", "address", "latitude", "longitude"):
        runner.true(f"schema_column_{column}", column in columns)

    user_id = upsert_user(
        telegram_id=FakeUser.id,
        username=FakeUser.username,
        full_name=FakeUser.full_name,
    )
    profile = get_or_create_patient_profile(user_id)
    runner.true("profile_exists", profile is not None)
    runner.check(
        "location_not_stored_initially",
        not has_location_stored(profile),
        repr(profile),
    )

    runner.true("update_trigger", is_location_update_trigger("Manzilni yangilash"))
    runner.eq("share_keyboard_button", build_share_location_keyboard().keyboard[0][0].text, SHARE_LOCATION_BUTTON)

    context = FakeContext()
    start_reply = asyncio.run(start(FakeUpdate(), context))
    runner.in_("start_asks_country", "mamlakat", start_reply.lower())
    runner.true("start_begins_registration", LOCATION_STATE_KEY in context.user_data)

    ask_ai_calls: list = []

    def track_ask_ai(*args, **kwargs):
        ask_ai_calls.append({"args": args, "kwargs": kwargs})
        return "AI javobi"

    with patch("app.handlers.chat.ask_ai", side_effect=track_ask_ai):
        registration_replies = asyncio.run(run_registration(context))

    runner.in_("registration_moves_to_region", "viloyat", registration_replies[0].lower())
    runner.true("registration_completed", "saqlandi" in registration_replies[-1].lower())
    runner.eq("registration_no_ai", len(ask_ai_calls), 0)
    runner.true("registration_state_cleared", LOCATION_STATE_KEY not in context.user_data)

    profile = get_patient_profile(user_id)
    runner.true("profile_has_location", profile is not None and has_location_stored(profile))
    if profile:
        runner.eq("profile_country", profile["country"], "O'zbekiston")
        runner.eq("profile_region", profile["region"], "Toshkent")
        runner.eq("profile_district", profile["district"], "Yunusobod")
        runner.eq("profile_address", profile["address"], "Amir Temur 12-uy")
        runner.eq("profile_city_region_sync", profile["city_region"], "Toshkent")

    gps_context = FakeContext()
    start_location_registration(gps_context)
    asyncio.run(send_text("O'zbekiston", gps_context))
    asyncio.run(send_text("Samarqand", gps_context))
    asyncio.run(send_text("Registon", gps_context))
    asyncio.run(send_text("Skip", gps_context))
    gps_reply = asyncio.run(send_location(39.6542, 66.9597, gps_context))
    runner.in_("gps_saved_reply", "saqlandi", gps_reply.lower())

    gps_profile = get_patient_profile(user_id)
    if gps_profile:
        runner.eq("gps_latitude", gps_profile["latitude"], 39.6542)
        runner.eq("gps_longitude", gps_profile["longitude"], 66.9597)

    stored_context = FakeContext()
    ask_ai_calls.clear()
    with patch("app.handlers.chat.ask_ai", side_effect=track_ask_ai):
        normal_reply, _ = asyncio.run(send_text("Bugun nima qilish kerak?", stored_context))
    runner.eq("stored_location_allows_ai", len(ask_ai_calls), 1)
    runner.eq("stored_location_ai_reply", normal_reply, "AI javobi")

    no_repeat_context = FakeContext()
    with patch("app.handlers.chat.ask_ai", side_effect=track_ask_ai):
        _, _ = asyncio.run(send_text("Salom", no_repeat_context))
    runner.true("no_repeat_registration", LOCATION_STATE_KEY not in no_repeat_context.user_data)

    update_context = FakeContext()
    with patch("app.handlers.chat.ask_ai", side_effect=track_ask_ai):
        update_reply, _ = asyncio.run(send_text("Manzilni yangilash", update_context))
    runner.true("update_trigger_starts_flow", LOCATION_STATE_KEY in update_context.user_data)
    runner.in_("update_trigger_prompt", "mamlakat", update_reply.lower())

    instructions = build_profile_instructions(get_patient_profile(user_id))
    runner.true("ai_context_has_location", instructions is not None)
    if instructions:
        runner.in_("ai_context_country", "country: O'zbekiston", instructions)
        runner.in_("ai_context_region", "region: Samarqand", instructions)
        runner.in_("ai_context_coordinates", "coordinates:", instructions)

    with patch("app.services.openai_service.client.responses.create") as mock_create:
        mock_create.return_value.output_text = "Umumiy ma'lumot."
        seed_location(user_id)
        profile = get_patient_profile(user_id)
        ask_ai("Salom", patient_profile=profile)
        instructions_sent = mock_create.call_args.kwargs["instructions"]
        runner.in_("ask_ai_location_injected", "Patient location", instructions_sent)

    if LEGACY_DB.exists():
        LEGACY_DB.unlink()
    import sqlite3

    legacy_conn = sqlite3.connect(LEGACY_DB)
    legacy_conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            full_name TEXT,
            created_at TEXT
        );
        CREATE TABLE patient_profiles (
            id INTEGER PRIMARY KEY,
            user_id INTEGER UNIQUE,
            full_name TEXT,
            age INTEGER,
            sex TEXT,
            phone_number TEXT,
            city_region TEXT,
            address TEXT,
            occupation TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        """
    )
    legacy_conn.commit()
    legacy_conn.close()

    os.environ["DATABASE_PATH"] = str(LEGACY_DB)
    from importlib import reload
    import app.config as app_config
    import app.db.connection as db_connection
    import app.settings as app_settings

    app_settings.get_settings.cache_clear()
    reload(app_settings)
    reload(app_config)
    reload(db_connection)
    db_connection.init_db()

    with db_connection.get_connection() as conn:
        legacy_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(patient_profiles)").fetchall()
        }
    runner.true("legacy_migration_country", "country" in legacy_columns)
    runner.true("legacy_migration_latitude", "latitude" in legacy_columns)
    os.environ["DATABASE_PATH"] = str(TEST_DB)
    app_settings.get_settings.cache_clear()
    reload(app_settings)
    reload(app_config)
    reload(db_connection)

    print()
    print("=" * 72)
    print(f"PHASE 5 STEP 2 VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)

    print("Phase 5 Step 2 OK: patient address and location verified")
    print("=" * 72)


if __name__ == "__main__":
    main()

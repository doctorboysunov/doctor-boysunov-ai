"""Simulate location registration handler with real DB profile + in-memory state."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_PATH"] = str(ROOT / "data" / "clinic.db")
os.environ["ADMIN_TELEGRAM_IDS"] = "7898074891"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "sim-token")
os.environ.setdefault("OPENAI_API_KEY", "sim-key")

from app.handlers.location import LOCATION_STATE_KEY, handle_location_registration_text
from app.repositories.patient_profile_repository import get_or_create_patient_profile
from app.services.location_profile import has_location_stored, is_skip_answer

TEXT = "Boshim og'riyapti"
USER_ID = 1


class FakeMessage:
    text = TEXT
    reply_text = AsyncMock()


class FakeUpdate:
    message = FakeMessage()


class FakeContext:
    user_data: dict = {LOCATION_STATE_KEY: {"step": "share_location", "updating": False}}


async def main() -> None:
    profile = get_or_create_patient_profile(USER_ID)
    print("=== DB patient_profiles (user_id=1) ===")
    for key in ("country", "region", "district", "address", "latitude", "longitude"):
        print(f"  {key}={profile.get(key)!r}")
    print(f"has_location_stored={has_location_stored(profile)}")
    print(f"is_skip_answer({TEXT!r})={is_skip_answer(TEXT)}")
    print(f"in-memory location_registration={FakeContext.user_data.get(LOCATION_STATE_KEY)!r}")

    handled = await handle_location_registration_text(
        FakeUpdate(),
        FakeContext(),
        user_id=USER_ID,
        conversation_id=1,
        patient_profile=profile,
    )
    print(f"handle_location_registration_text returned {handled}")
    print(f"in-memory after={FakeContext.user_data.get(LOCATION_STATE_KEY)!r}")
    if FakeMessage.reply_text.await_args:
        print(f"bot would reply: {FakeMessage.reply_text.await_args.args[0]!r}")


if __name__ == "__main__":
    asyncio.run(main())

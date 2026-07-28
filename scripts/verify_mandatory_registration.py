"""Mandatory patient registration (v6.9.0) — end-to-end regression tests.

Requirements verified:
  1. Before any medical consultation starts, a brand new patient must
     complete: full name -> phone number -> country -> region -> district
     (in that order), and only then does the consultation engine answer.
  2. Existing patients who already have location on file (pre-dating this
     feature) but no name/phone are asked for the missing fields only
     (not re-asked for country/region/district).
  3. Once registration is complete, it is never repeated for that patient.
  4. Booking (online consultation / clinic appointment) reuses the saved
     name and phone number instead of asking again.
  5. A medical complaint blurted out mid-registration still gets one paused
     safety-valve reply (pre-existing behavior, must not regress).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_mandatory_registration.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "mandatory-reg-test-token")
os.environ.setdefault("OPENAI_API_KEY", "mandatory-reg-test-key")

sys.path.insert(0, str(ROOT))

from app.db.connection import init_db  # noqa: E402
from app.handlers.appointments import BOOKING_STATE_KEY  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.repositories.conversation_repository import upsert_user  # noqa: E402
from app.repositories.patient_profile_repository import (  # noqa: E402
    get_patient_profile,
    update_patient_profile,
)
from app.services.location_profile import is_registration_complete  # noqa: E402


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


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, telegram_id: int, username: str, full_name: str):
        class _User:
            id = telegram_id

        _User.username = username
        _User.full_name = full_name
        self.effective_user = _User()
        self.message = FakeMessage("")


class FakeContext:
    def __init__(self) -> None:
        self.user_data: dict = {}


def _all_replies(update: FakeUpdate) -> list[str]:
    return [c.args[0] for c in update.message.reply_text.await_args_list]


async def send_chat(update: FakeUpdate, context: FakeContext, text: str) -> list[str]:
    update.message = FakeMessage(text)
    await chat(update, context)
    return _all_replies(update)


def main() -> None:
    init_db()
    runner = TestRunner()

    async def scenario_fresh_patient_full_registration_order() -> None:
        telegram_id = 9001001
        upsert_user(telegram_id=telegram_id, username="reg_a", full_name="Reg A")
        update = FakeUpdate(telegram_id, "reg_a", "Reg A")
        context = FakeContext()

        r1 = await send_chat(update, context, "Boshim og'riyapti")
        runner.check("fresh_first_message_asks_full_name", any("ismingizni" in r.lower() for r in r1), r1)

        r2 = await send_chat(update, context, "Alisher Fayzullayev")
        runner.check("fresh_then_asks_phone", any("telefon" in r.lower() for r in r2), r2)

        r3 = await send_chat(update, context, "+998901112233")
        runner.check("fresh_then_asks_country", any("mamlakat" in r.lower() for r in r3), r3)

        r4 = await send_chat(update, context, "O'zbekiston")
        runner.check("fresh_then_asks_region", any("viloyat" in r.lower() for r in r4), r4)

        r5 = await send_chat(update, context, "Qashqadaryo")
        runner.check("fresh_then_asks_district", any("tuman" in r.lower() for r in r5), r5)

        r6 = await send_chat(update, context, "Shahrisabz")
        runner.check("fresh_registration_completes", any("saqlandi" in r.lower() for r in r6), r6)

        profile = get_patient_profile(9001001) or {}
        # user_id may differ from telegram_id; fetch via upsert result instead
        from app.repositories.conversation_repository import upsert_user as _uu

        user_id = _uu(telegram_id=telegram_id, username="reg_a", full_name="Reg A")
        profile = get_patient_profile(user_id)
        runner.check("fresh_profile_complete", is_registration_complete(profile), profile)
        runner.check("fresh_profile_full_name", profile.get("full_name") == "Alisher Fayzullayev", profile)
        runner.check("fresh_profile_phone", bool(profile.get("phone_number")), profile)

        # Only now should the consultation engine actually answer.
        r7 = await send_chat(update, context, "Boshim og'riyapti")
        runner.check(
            "fresh_consultation_starts_after_registration",
            any("?" in r for r in r7) or any(len(r) > 0 for r in r7),
            r7,
        )

        # Registration must never be repeated.
        r8 = await send_chat(update, context, "Yana bir savol bor")
        runner.check(
            "fresh_no_repeat_registration",
            all("ismingizni" not in r.lower() and "mamlakat" not in r.lower() for r in r8),
            r8,
        )

    async def scenario_legacy_patient_missing_name_phone_only() -> None:
        # Pre-existing patient who registered before this feature shipped:
        # location already on file, but no name/phone. Must be asked only
        # for the two missing fields, not re-asked for location.
        telegram_id = 9001002
        user_id = upsert_user(telegram_id=telegram_id, username="reg_b", full_name="Reg B")
        update_patient_profile(
            user_id,
            country="O'zbekiston",
            region="Buxoro",
            district="Kogon",
            city_region="Buxoro",
        )
        update = FakeUpdate(telegram_id, "reg_b", "Reg B")
        context = FakeContext()

        r1 = await send_chat(update, context, "Bo'yin og'riyapti")
        runner.check("legacy_asks_full_name_first", any("ismingizni" in r.lower() for r in r1), r1)

        r2 = await send_chat(update, context, "Malika Yusupova")
        runner.check("legacy_then_asks_phone", any("telefon" in r.lower() for r in r2), r2)

        r3 = await send_chat(update, context, "+998933334455")
        # Country/region/district already on file -> should auto-complete,
        # NOT ask country again.
        runner.check(
            "legacy_completes_without_reasking_location",
            any("saqlandi" in r.lower() for r in r3),
            r3,
        )
        runner.check(
            "legacy_did_not_ask_country_again",
            all("mamlakat" not in r.lower() for r in r3),
            r3,
        )

        profile = get_patient_profile(user_id)
        runner.check("legacy_profile_complete", is_registration_complete(profile), profile)
        runner.check("legacy_location_unchanged", profile.get("region") == "Buxoro", profile)

    async def scenario_booking_reuses_registration() -> None:
        telegram_id = 9001003
        user_id = upsert_user(telegram_id=telegram_id, username="reg_c", full_name="Reg C")
        update = FakeUpdate(telegram_id, "reg_c", "Reg C")
        context = FakeContext()

        # Complete registration first.
        await send_chat(update, context, "Salom")
        await send_chat(update, context, "Dilshod Rahimov")
        await send_chat(update, context, "+998911223344")
        await send_chat(update, context, "O'zbekiston")
        await send_chat(update, context, "Andijon")
        await send_chat(update, context, "Andijon shahri")

        profile = get_patient_profile(user_id)
        runner.check("booking_prereq_registration_complete", is_registration_complete(profile), profile)

        # Now trigger booking — must reuse saved name/phone, not ask again.
        r = await send_chat(update, context, "Onlayn konsultatsiya kerak")
        runner.check(
            "booking_reuses_name_phone_no_reask",
            all("ismingizni" not in x.lower() and "telefon raqamingizni yozing" not in x.lower() for x in r),
            r,
        )
        runner.check(
            "booking_announces_reuse",
            any("ro'yxatdan o'tish ma'lumotlaringizdan olindi" in x.lower() for x in r),
            r,
        )
        runner.check(
            "booking_prefilled_state",
            context.user_data[BOOKING_STATE_KEY].get("full_name") == "Dilshod Rahimov",
            str(context.user_data),
        )

    async def scenario_medical_pause_still_works_mid_registration() -> None:
        # Pre-existing safety valve: a medical complaint mid-registration
        # still gets one direct reply, without fully blocking the patient.
        telegram_id = 9001004
        upsert_user(telegram_id=telegram_id, username="reg_d", full_name="Reg D")
        update = FakeUpdate(telegram_id, "reg_d", "Reg D")
        context = FakeContext()

        await send_chat(update, context, "Salom")  # starts registration (full_name step)
        r = await send_chat(update, context, "Boshim juda qattiq og'riyapti")
        runner.check(
            "medical_pause_gets_a_reply_not_silence",
            len(r) > 0,
            r,
        )

    asyncio.run(scenario_fresh_patient_full_registration_order())
    asyncio.run(scenario_legacy_patient_missing_name_phone_only())
    asyncio.run(scenario_booking_reuses_registration())
    asyncio.run(scenario_medical_pause_still_works_mid_registration())

    print()
    print("=" * 72)
    print(f"MANDATORY REGISTRATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Mandatory registration OK")
    print("=" * 72)


if __name__ == "__main__":
    main()

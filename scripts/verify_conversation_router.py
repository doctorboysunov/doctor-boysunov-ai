"""Conversation router v6.8.0 — end-to-end chat.py regression tests.

Covers the two bugs reported by the user:
  1. Mid-consultation booking phrases ("Book me", "Onlayn konsultatsiya", ...)
     must immediately hand off to the structured booking wizard instead of
     falling back to the generic "Konsultatsiyamiz davom etmoqda" text.
  2. A confirmed emergency always outranks booking, even before the
     consultation engine is reached (chat.py-level priority).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_conversation_router.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "router-test-token")
os.environ.setdefault("OPENAI_API_KEY", "router-test-key")

sys.path.insert(0, str(ROOT))

from app.db.connection import init_db  # noqa: E402
from app.handlers.appointments import BOOKING_STATE_KEY  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.repositories.appointment_repository import get_patient_appointments  # noqa: E402
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

    async def scenario_mid_consult_booking() -> None:
        telegram_id = 8801001
        user_id = upsert_user(telegram_id=telegram_id, username="router_a", full_name="Router A")
        seed_default_location(user_id)
        update = FakeUpdate(telegram_id, "router_a", "Router A")
        context = FakeContext()

        r1 = await send_chat(update, context, "Chap oyoq og'riyapti, beldan tarqaladi")
        runner.check("consult_started_asks_question", any("?" in r for r in r1), r1)

        r2 = await send_chat(update, context, "Meni band qiling, onlayn konsultatsiya kerak")
        runner.check(
            "booking_phrase_not_canned_fallback",
            all("oldingi ma'lumotlaringiz saqlangan" not in r.lower() for r in r2),
            r2,
        )
        # Registration is mandatory before consultation, so this patient
        # (seeded via seed_default_location) already has name + phone on
        # file — booking must reuse them and skip straight to the date.
        runner.check(
            "booking_phrase_reuses_saved_name_and_phone",
            any("ro'yxatdan o'tish ma'lumotlaringizdan olindi" in r.lower() for r in r2),
            r2,
        )
        runner.check(
            "booking_phrase_starts_at_date_step",
            any("qaysi sanada" in r.lower() for r in r2),
            r2,
        )
        runner.check(
            "booking_state_set_after_handoff",
            bool(context.user_data.get(BOOKING_STATE_KEY)),
            str(context.user_data),
        )
        runner.check(
            "booking_state_prefilled_name_phone",
            context.user_data[BOOKING_STATE_KEY].get("full_name") == "Test Patient"
            and bool(context.user_data[BOOKING_STATE_KEY].get("phone_number")),
            str(context.user_data),
        )

        # Continue the (shortened) booking wizard end-to-end — name/phone are
        # already known, so only date/time/complaint/confirm remain.
        r3 = await send_chat(update, context, "2026-08-20")
        runner.check("booking_step_time_prompt", any("vaqt" in r.lower() for r in r3), r3)
        r4 = await send_chat(update, context, "11:00")
        runner.check("booking_step_complaint_prompt", any("shikoyat" in r.lower() for r in r4), r4)
        r5 = await send_chat(update, context, "Chap oyoq og'rig'i")
        runner.check("booking_step_confirm_summary", any("tasdiqlash" in r.lower() for r in r5), r5)
        r6 = await send_chat(update, context, "Ha")
        runner.check(
            "booking_completes_creates_appointment",
            len(get_patient_appointments(user_id)) >= 1,
            str(get_patient_appointments(user_id)),
        )

    async def scenario_emergency_outranks_booking() -> None:
        telegram_id = 8801002
        user_id = upsert_user(telegram_id=telegram_id, username="router_b", full_name="Router B")
        seed_default_location(user_id)
        update = FakeUpdate(telegram_id, "router_b", "Router B")
        context = FakeContext()

        replies = await send_chat(
            update,
            context,
            "Birdan yuzim qiyshayib qoldi, gapira olmayapman, qo'lim ishlamay qoldi, band qiling",
        )
        runner.check(
            "emergency_outranks_booking_no_wizard_started",
            not bool(context.user_data.get(BOOKING_STATE_KEY)),
            str(context.user_data),
        )
        runner.check(
            "emergency_reply_is_urgent",
            any("103" in r or "shoshilinch" in r.lower() for r in replies),
            replies,
        )

    async def scenario_english_booking_phrases() -> None:
        for idx, phrase in enumerate(("Book me", "Appointment", "Call me", "I want an online consultation")):
            telegram_id = 8801100 + idx
            user_id = upsert_user(telegram_id=telegram_id, username=f"router_c{idx}", full_name="Router C")
            seed_default_location(user_id)
            update = FakeUpdate(telegram_id, f"router_c{idx}", "Router C")
            context = FakeContext()
            replies = await send_chat(update, context, phrase)
            runner.check(
                f"fresh_booking_phrase_reuses_registration:{phrase}",
                any("qaysi sanada" in r.lower() for r in replies),
                replies,
            )

    async def scenario_mid_consult_exact_reported_phrases() -> None:
        # Follow-up bug report — each of these literal phrases, sent as the
        # very next message after a consultation has already asked its first
        # clinical question, must leave the questioning flow immediately and
        # never fall back to the generic "Konsultatsiyamiz davom etmoqda"
        # text (tested independently so no phrase's booking wizard consumes
        # the next phrase as an answer).
        phrases = (
            "Online consultation",
            "I want an appointment",
            "I need consultation",
            "Book me",
            "Clinic appointment",
        )
        for idx, phrase in enumerate(phrases):
            telegram_id = 8801200 + idx
            user_id = upsert_user(telegram_id=telegram_id, username=f"router_d{idx}", full_name="Router D")
            seed_default_location(user_id)
            update = FakeUpdate(telegram_id, f"router_d{idx}", "Router D")
            context = FakeContext()
            r1 = await send_chat(update, context, "Chap oyoq og'riyapti, beldan tarqaladi")
            runner.check(f"reported_phrase_consult_started:{phrase}", any("?" in r for r in r1), r1)
            r2 = await send_chat(update, context, phrase)
            runner.check(
                f"reported_phrase_leaves_questioning:{phrase}",
                all(r not in r1 for r in r2),
                r2,
            )
            runner.check(
                f"reported_phrase_no_canned_fallback:{phrase}",
                all(
                    "oldingi ma'lumotlaringiz saqlangan" not in r.lower() and "davom etmoqda" not in r.lower()
                    for r in r2
                ),
                r2,
            )
            runner.check(
                f"reported_phrase_starts_booking_wizard:{phrase}",
                any("qaysi sanada" in r.lower() for r in r2),
                r2,
            )
            runner.check(
                f"reported_phrase_booking_state_set:{phrase}",
                bool(context.user_data.get(BOOKING_STATE_KEY)),
                str(context.user_data),
            )

    async def scenario_repeated_booking_phrases_during_wizard() -> None:
        # Latest bug report — once booking is triggered, repeating another
        # booking-intent phrase (instead of answering the wizard's current
        # question) must NEVER fall back to the consultation engine's
        # "Konsultatsiyamiz davom etmoqda" text, and must never leave the
        # booking workflow (state-machine lock, not a prompt fix).
        telegram_id = 8801300
        user_id = upsert_user(telegram_id=telegram_id, username="router_repeat", full_name="Router Repeat")
        seed_default_location(user_id)
        update = FakeUpdate(telegram_id, "router_repeat", "Router Repeat")
        context = FakeContext()

        r1 = await send_chat(update, context, "Chap oyoq og'riyapti, beldan tarqaladi")
        runner.check("repeat_consult_started", any("?" in r for r in r1), r1)

        r2 = await send_chat(update, context, "Online consultation")
        # Name + phone are already registered (seed_default_location), so the
        # wizard starts straight at the date step.
        runner.check("repeat_first_trigger_starts_wizard", any("qaysi sanada" in r.lower() for r in r2), r2)

        for phrase in ("Online consultation", "I need consultation", "Book me", "Appointment"):
            r = await send_chat(update, context, phrase)
            runner.check(
                f"repeat_no_canned_fallback:{phrase}",
                all(
                    "oldingi ma'lumotlaringiz saqlangan" not in x.lower() and "davom etmoqda" not in x.lower()
                    for x in r
                ),
                r,
            )
            runner.check(
                f"repeat_still_in_booking_state:{phrase}",
                bool(context.user_data.get(BOOKING_STATE_KEY)),
                str(context.user_data),
            )
            booking_after = context.user_data.get(BOOKING_STATE_KEY) or {}
            runner.check(
                f"repeat_did_not_corrupt_appointment_date:{phrase}",
                booking_after.get("appointment_date") is None,
                str(booking_after),
            )
            runner.check(
                f"repeat_still_on_date_step:{phrase}",
                booking_after.get("step") == "appointment_date",
                str(booking_after),
            )

        # After the repeats, a real answer must still progress the wizard
        # normally and let the patient finish booking end-to-end.
        r3 = await send_chat(update, context, "2026-08-05")
        runner.check("repeat_then_date_advances", any("vaqt" in x.lower() for x in r3), r3)
        r4 = await send_chat(update, context, "10:00")
        runner.check("repeat_then_time_advances", any("shikoyat" in x.lower() for x in r4), r4)
        r5 = await send_chat(update, context, "Oyoq og'riyapti")
        runner.check(
            "repeat_then_complaint_shows_confirmation",
            any("tasdiqlash" in x.lower() for x in r5),
            r5,
        )
        r6 = await send_chat(update, context, "Ha")
        runner.check(
            "repeat_then_confirm_completes_booking",
            any("qabul qilindi" in x.lower() for x in r6),
            r6,
        )
        runner.check(
            "repeat_booking_state_cleared_after_completion",
            not context.user_data.get(BOOKING_STATE_KEY),
            str(context.user_data),
        )
        appointments = get_patient_appointments(user_id)
        runner.check(
            "repeat_appointment_actually_created",
            len(appointments) == 1 and appointments[0]["patient_full_name"] == "Test Patient",
            appointments,
        )

    async def scenario_booking_asks_name_phone_when_not_registered() -> None:
        # A brand new patient (no registration on file yet) triggering
        # booking as their very first message must still be asked for name
        # and phone — there is nothing saved to reuse yet.
        telegram_id = 8801500
        user_id = upsert_user(telegram_id=telegram_id, username="router_unreg", full_name="Router Unreg")
        update = FakeUpdate(telegram_id, "router_unreg", "Router Unreg")
        context = FakeContext()

        r1 = await send_chat(update, context, "Book me an appointment")
        runner.check(
            "unregistered_booking_asks_full_name",
            any("ismingizni" in r.lower() for r in r1),
            r1,
        )
        runner.check(
            "unregistered_booking_no_reuse_message",
            all("ro'yxatdan o'tish ma'lumotlaringizdan olindi" not in r.lower() for r in r1),
            r1,
        )

        r2 = await send_chat(update, context, "Kamola Kamolova")
        runner.check("unregistered_booking_asks_phone", any("telefon" in r.lower() for r in r2), r2)
        r3 = await send_chat(update, context, "+998933332211")
        runner.check("unregistered_booking_asks_date", any("qaysi sanada" in r.lower() for r in r3), r3)
        await send_chat(update, context, "2026-08-10")
        await send_chat(update, context, "09:00")
        await send_chat(update, context, "Bosh og'rig'i")
        await send_chat(update, context, "Ha")

        # Completing the wizard must also populate the shared patient profile
        # (mandatory-registration reuse in reverse — booking data feeds back
        # into registration, so a later consultation won't ask again either).
        from app.repositories.patient_profile_repository import get_patient_profile

        profile = get_patient_profile(user_id)
        runner.check(
            "unregistered_booking_saves_name_to_profile",
            profile is not None and profile.get("full_name") == "Kamola Kamolova",
            profile,
        )
        runner.check(
            "unregistered_booking_saves_phone_to_profile",
            profile is not None and bool(profile.get("phone_number")),
            profile,
        )

    async def scenario_corrupted_step_never_leaks_to_consultation() -> None:
        # Defensive state-machine repair: an unexpected/corrupted booking
        # step value must never fall through to `return False` (which would
        # leak the message into the consultation engine). It must repair
        # itself and stay locked in the booking wizard.
        telegram_id = 8801400
        upsert_user(telegram_id=telegram_id, username="router_corrupt", full_name="Router Corrupt")
        update = FakeUpdate(telegram_id, "router_corrupt", "Router Corrupt")
        context = FakeContext()
        context.user_data[BOOKING_STATE_KEY] = {"step": "some_unknown_step"}

        r = await send_chat(update, context, "hello")
        runner.check(
            "corrupted_step_repairs_to_full_name",
            any("ismingizni" in x.lower() for x in r),
            r,
        )
        runner.check(
            "corrupted_step_still_locked_in_booking",
            bool(context.user_data.get(BOOKING_STATE_KEY)),
            str(context.user_data),
        )

    asyncio.run(scenario_mid_consult_booking())
    asyncio.run(scenario_emergency_outranks_booking())
    asyncio.run(scenario_english_booking_phrases())
    asyncio.run(scenario_mid_consult_exact_reported_phrases())
    asyncio.run(scenario_repeated_booking_phrases_during_wizard())
    asyncio.run(scenario_booking_asks_name_phone_when_not_registered())
    asyncio.run(scenario_corrupted_step_never_leaks_to_consultation())

    print()
    print("=" * 72)
    print(f"CONVERSATION ROUTER: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Conversation router OK")
    print("=" * 72)


if __name__ == "__main__":
    main()

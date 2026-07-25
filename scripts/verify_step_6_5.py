"""Phase 6.5: intelligent patient creation engine verification."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_6_5.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["PATIENT_INTAKE_API_KEY"] = "test-intake-key"
os.environ["ADMIN_TELEGRAM_IDS"] = "940001"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "intake-65-test-token")
os.environ.setdefault("OPENAI_API_KEY", "intake-65-test-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.db.connection import get_connection, init_db  # noqa: E402
from app.handlers.admin_conversation import handle_admin_chat_text  # noqa: E402
from app.handlers.patient_intake import (  # noqa: E402
    handle_patient_contact,
    handle_patient_voice,
)
from app.repositories.follow_up_repository import (  # noqa: E402
    list_due_follow_ups,
    list_follow_ups_for_patient,
)
from app.repositories.medical_history_repository import get_medical_history  # noqa: E402
from app.repositories.patient_intake_repository import (  # noqa: E402
    find_patient_by_phone,
    search_patients,
)
from app.repositories.treatment_repository import get_active_treatment  # noqa: E402
from app.services.follow_up_scheduler import (  # noqa: E402
    add_months,
    build_initial_follow_up_dates,
)
from app.services.patient_creation_engine import (  # noqa: E402
    create_patient_intelligently,
    format_creation_summary,
)
from app.services.patient_intake.extraction import extract_patient_from_text  # noqa: E402
from app.services.patient_intake.phone import normalize_phone  # noqa: E402


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


class FakeUser:
    id = 940001
    username = "doctor_user"
    full_name = "Doctor User"


class FakeContact:
    first_name = "Ali"
    last_name = "Valiyev"
    phone_number = "+998901234567"


class FakeMessage:
    def __init__(self, text: str | None = None, contact: FakeContact | None = None):
        self.text = text
        self.contact = contact
        self.voice = None
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, message: FakeMessage) -> None:
        self.effective_user = FakeUser()
        self.message = message


class FakeContext:
    user_data: dict = {}


def main() -> None:
    runner = TestRunner()
    init_db()

    treatment_start = "2026-03-01"
    planned = build_initial_follow_up_dates(date.fromisoformat(treatment_start))
    runner.eq("schedule_has_six_steps", len(planned), 6)
    runner.eq("first_check_in_10d", planned[0][1], date(2026, 3, 11))
    runner.eq("second_check_in_20d", planned[1][1], date(2026, 3, 21))

    # 1. Text input — full intelligent creation
    text_result = create_patient_intelligently(
        source="telegram",
        text="Ali Valiyev\n+998901234567",
        started_at=treatment_start,
    )
    runner.true = lambda name, value: runner.check(name, bool(value), repr(value))
    runner.true("text_creation", text_result is not None)
    if text_result:
        runner.true("patient_created", text_result.created)
        runner.true("treatment_started", text_result.treatment_started)
        runner.eq("patient_name", text_result.full_name, "Ali Valiyev")
        runner.eq("patient_phone", text_result.phone_number, "+998901234567")
        runner.check("unique_patient_id", text_result.patient_id > 0, str(text_result.patient_id))
        runner.check("medical_record_created", text_result.medical_record_id is not None, "")
        runner.eq("follow_up_count", text_result.follow_up_count, 7)
        runner.eq("first_follow_up_date", text_result.follow_up_dates[0], "2026-03-11")
        expected_sixth = planned[5][1].isoformat()
        runner.eq("sixth_follow_up_date", text_result.follow_up_dates[5], expected_sixth)

        records = get_medical_history(text_result.patient_id)
        runner.check("consultation_record", any(r["record_type"] == "consultation" for r in records), "")
        treatment = get_active_treatment(text_result.patient_id)
        runner.true("active_treatment", treatment is not None)
        if treatment:
            runner.eq("treatment_start", treatment["started_at"], treatment_start)

        summary = format_creation_summary(text_result)
        runner.check("summary_has_patient_id", "Patient ID:" in summary, summary)
        runner.check("summary_has_followups", "Kuzatuvlar:" in summary, summary)

    # 2. Duplicate prevention by phone
    duplicate = create_patient_intelligently(
        source="web",
        text="Ali Valiyev 901234567",
        started_at=treatment_start,
    )
    runner.true("duplicate_found", duplicate is not None)
    if duplicate and text_result:
        runner.eq("duplicate_same_id", duplicate.patient_id, text_result.patient_id)
        runner.check("duplicate_prevented", duplicate.duplicate_prevented, "")
        runner.check("no_second_treatment", not duplicate.treatment_started, "")

    with get_connection() as conn:
        profile_count = conn.execute("SELECT COUNT(*) AS c FROM patient_profiles").fetchone()["c"]
    runner.eq("single_profile_by_phone", profile_count, 1)

    # 3. Search immediately after creation
    by_phone = find_patient_by_phone("901234567")
    runner.true("searchable_by_phone", by_phone is not None)
    by_name = search_patients("Ali Valiyev")
    runner.check("searchable_by_name", len(by_name) >= 1, repr(by_name))

    # 4. Contact input
    contact_result = create_patient_intelligently(
        source="contact",
        full_name="Sardor Karimov",
        phone_number="909876543",
        started_at=treatment_start,
    )
    runner.true("contact_creation", contact_result is not None and contact_result.created)
    if contact_result:
        runner.eq("contact_follow_ups", contact_result.follow_up_count, 7)

    # 5. Voice input (mocked transcription)
    with patch(
        "app.services.patient_intake.service.transcribe_audio",
        return_value="Dilnoza Karimova 909112233",
    ):
        voice_result = create_patient_intelligently(
            source="voice",
            audio_bytes=b"fake-audio",
            started_at=treatment_start,
        )
    runner.true("voice_creation", voice_result is not None and voice_result.created)
    if voice_result:
        runner.eq("voice_name", voice_result.full_name, "Dilnoza Karimova")
        runner.eq("voice_follow_ups", voice_result.follow_up_count, 7)

    # 6. OCR input (mocked vision)
    with patch("app.services.patient_intake.service.extract_patient_from_image") as mock_ocr:
        from app.services.patient_intake.extraction import ExtractedPatient

        mock_ocr.return_value = ExtractedPatient(
            full_name="Olim Olimov",
            phone_number="+998907776655",
        )
        ocr_result = create_patient_intelligently(
            source="ocr",
            image_bytes=b"fake-image",
            started_at=treatment_start,
        )
    runner.true("ocr_creation", ocr_result is not None and ocr_result.created)
    if ocr_result:
        runner.eq("ocr_follow_ups", ocr_result.follow_up_count, 7)

    # 7. Reminder jobs — due follow-ups queryable
    due = list_due_follow_ups(as_of_date="2026-03-11")
    runner.check(
        "reminder_job_ready",
        any(item["patient_id"] == text_result.patient_id for item in due) if text_result else False,
        repr(due),
    )

    # 8. Persistence across restart
    init_db()
    reloaded = list_follow_ups_for_patient(text_result.patient_id) if text_result else []
    runner.eq("survives_restart", len(reloaded), 7)

    # 9. Telegram handler integration
    async def run_text_handler() -> str:
        update = FakeUpdate(FakeMessage(text="Nodira Yusupova 901010101"))
        handled = await handle_admin_chat_text(update, FakeContext())
        if not handled:
            return ""
        return update.message.reply_text.await_args.args[0]

    reply = asyncio.run(run_text_handler())
    runner.check("telegram_handler", "Patient created" in reply and "Follow-ups scheduled" in reply, reply)

    async def run_contact_handler() -> str:
        update = FakeUpdate(FakeMessage(contact=FakeContact()))
        await handle_patient_contact(update, FakeContext())
        return update.message.reply_text.await_args.args[0]

    contact_reply = asyncio.run(run_contact_handler())
    runner.check("telegram_contact_summary", "Patient ID" in contact_reply, contact_reply)

    async def run_voice_handler() -> str:
        from unittest.mock import MagicMock

        update = FakeUpdate(FakeMessage())
        voice = MagicMock()
        voice.file_id = "voice-test-id"
        update.message.voice = voice
        update.message.audio = None

        file_obj = MagicMock()
        file_obj.file_path = "voice/test.oga"
        file_obj.download_as_bytearray = AsyncMock(return_value=bytearray(b"fake"))

        context = FakeContext()
        context.bot = MagicMock()
        context.bot.get_file = AsyncMock(return_value=file_obj)

        with patch(
            "app.handlers.patient_intake.transcribe_audio",
            return_value="Test Voice 901212121",
        ):
            await handle_patient_voice(update, context)
        return update.message.reply_text.await_args.args[0]

    voice_reply = asyncio.run(run_voice_handler())
    runner.check("telegram_voice_summary", "Patient ID" in voice_reply, voice_reply)

    # 10. API endpoints
    from fastapi.testclient import TestClient  # noqa: E402
    from app.api.patient_intake_api import app  # noqa: E402

    client = TestClient(app)
    headers = {"X-API-Key": "test-intake-key"}

    create_resp = client.post(
        "/api/v1/patients/create",
        headers=headers,
        json={
            "source": "web",
            "full_name": "Web Patient",
            "phone_number": "909998877",
        },
    )
    runner.eq("api_create_status", create_resp.status_code, 200)
    create_body = create_resp.json()
    runner.eq("api_create_follow_ups", create_body["follow_up_count"], 7)
    runner.true("api_treatment_started", create_body["treatment_started"])

    mobile_resp = client.post(
        "/api/v1/patients/capture",
        headers=headers,
        json={
            "source": "mobile",
            "text": "Mobile Patient 901313131",
        },
    )
    runner.eq("mobile_capture_status", mobile_resp.status_code, 200)
    mobile_body = mobile_resp.json()
    runner.check("mobile_has_treatment", mobile_body.get("treatment_id") is not None, mobile_body)

    search_resp = client.get(
        "/api/v1/patients/search",
        headers=headers,
        params={"q": "Ali"},
    )
    runner.eq("search_api_status", search_resp.status_code, 200)
    search_body = search_resp.json()
    runner.check("search_api_results", len(search_body["patients"]) >= 1, search_body)

    print()
    print("=" * 72)
    print(f"PHASE 6.5 VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)

    print("Phase 6.5 OK: intelligent patient creation engine verified")
    print("=" * 72)


if __name__ == "__main__":
    main()

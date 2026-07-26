"""Phase 6: universal patient capture verification."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_6.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["PATIENT_INTAKE_API_KEY"] = "test-intake-key"
os.environ["ADMIN_TELEGRAM_IDS"] = "930001"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "intake-test-token")
os.environ["OPENAI_API_KEY"] = "intake-test-key"

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
from app.repositories.medical_history_repository import get_medical_history  # noqa: E402
from app.repositories.patient_intake_repository import find_patient_by_phone  # noqa: E402
from app.services.patient_intake.clinical_form import (  # noqa: E402
    extract_clinical_form,
    is_clinical_form_text,
)
from app.services.patient_intake.extraction import extract_patient_from_text  # noqa: E402
from app.services.patient_intake.phone import normalize_phone  # noqa: E402
from app.services.patient_creation_engine import create_patient_intelligently  # noqa: E402
from app.services.patient_intake.service import capture_clinical_form, capture_patient  # noqa: E402


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
    id = 930001
    username = "capture_user"
    full_name = "Capture User"


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

    with get_connection() as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(patient_profiles)").fetchall()
        }
        user_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }

    runner.check("phone_normalized_column", "phone_normalized" in columns, repr(columns))
    runner.check("registration_source_column", "registration_source" in user_columns, repr(user_columns))

    extracted = extract_patient_from_text("Ali Valiyev 901234567")
    runner.true = lambda name, value: runner.check(name, bool(value), repr(value))
    runner.true("text_extract_name", extracted and extracted.full_name == "Ali Valiyev")
    runner.eq("text_extract_phone", extracted.phone_number if extracted else None, "+998901234567")

    extracted_voice_text = extract_patient_from_text("Ali Valiyev. Phone 90 123 45 67.")
    runner.true("voice_text_extract", extracted_voice_text is not None)
    if extracted_voice_text:
        runner.eq("voice_text_phone", extracted_voice_text.phone_number, "+998901234567")

    first = capture_patient(source="web", text="Ali Valiyev 901234567")
    runner.true("web_capture_created", first is not None and first.created)
    if first:
        runner.eq("web_patient_name", first.full_name, "Ali Valiyev")
        patient_id = first.patient_id

    duplicate = capture_patient(source="mobile", text="Ali Valiyev 90 123 45 67")
    runner.true("duplicate_not_created", duplicate is not None and not duplicate.created)
    if duplicate and first:
        runner.eq("duplicate_same_id", duplicate.patient_id, first.patient_id)

    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM patient_profiles WHERE phone_normalized = ?",
            (normalize_phone("901234567"),),
        ).fetchone()["c"]
    runner.eq("sqlite_single_phone_row", count, 1)

    init_db()
    reloaded = find_patient_by_phone("901234567")
    runner.true("survives_restart", reloaded is not None)

    async def run_contact() -> str:
        update = FakeUpdate(FakeMessage(contact=FakeContact()))
        await handle_patient_contact(update, FakeContext())
        return update.message.reply_text.await_args.args[0]

    reply = asyncio.run(run_contact())
    runner.check("telegram_contact_capture", "Patient ID" in reply, reply)

    async def run_text_capture() -> str:
        from app.domain.admin_conversation_state import enter_patient_registration_mode  # noqa: E402

        ctx = FakeContext()
        enter_patient_registration_mode(ctx, admin_telegram_id=930001)
        update = FakeUpdate(FakeMessage(text="Sardor Karimov 909876543"))
        await handle_admin_chat_text(update, ctx)
        return update.message.reply_text.await_args.args[0]

    capture_reply = asyncio.run(run_text_capture())
    runner.check("telegram_text_capture", "Patient ID" in capture_reply, capture_reply)

    with patch(
        "app.services.patient_intake.service.transcribe_audio",
        return_value="Ali Valiyev 901111222",
    ):
        voice_result = capture_patient(source="voice", audio_bytes=b"fake-audio")
    runner.true("voice_capture", voice_result is not None)

    with patch("app.services.patient_intake.service.extract_patient_from_image") as mock_image:
        from app.services.patient_intake.extraction import ExtractedPatient

        mock_image.return_value = ExtractedPatient(
            full_name="Olim Olimov",
            phone_number="+998907776655",
        )
        ocr_result = capture_patient(source="ocr", image_bytes=b"fake-image")

    runner.true("ocr_capture", ocr_result is not None)
    if ocr_result:
        runner.eq("ocr_name", ocr_result.full_name, "Olim Olimov")

    from fastapi.testclient import TestClient  # noqa: E402
    from app.api.patient_intake_api import app  # noqa: E402

    client = TestClient(app)
    health = client.get("/api/v1/health")
    runner.eq("api_health", health.status_code, 200)

    api_create = client.post(
        "/api/v1/patients/capture",
        headers={"X-API-Key": "test-intake-key"},
        json={
            "source": "web",
            "full_name": "Web Patient",
            "phone_number": "909998877",
        },
    )
    runner.eq("api_create_status", api_create.status_code, 200)
    body = api_create.json()
    runner.eq("api_create_name", body["full_name"], "Web Patient")
    runner.eq("api_create_source", body["source"], "web")

    mobile_resp = client.post(
        "/api/v1/patients/capture",
        headers={"X-API-Key": "test-intake-key"},
        json={
            "source": "mobile",
            "text": "Mobile Patient 901010101",
        },
    )
    runner.eq("mobile_text_status", mobile_resp.status_code, 200)

    clinical_text = (
        "Ism: Dilnoza\n"
        "Familiya: Karimova\n"
        "Telefon: 909112233\n"
        "Tashxis: Servikal osteoxondroz\n"
        "Shikoyat: Bo'yin og'rig'i\n"
        "Davolash: Fizioterapiya kursi\n"
        "Keyingi kuzatuv: 10 kun"
    )
    runner.true("clinical_form_detect", is_clinical_form_text(clinical_text))
    parsed = extract_clinical_form(clinical_text)
    runner.true("clinical_form_parse", parsed is not None)
    if parsed:
        runner.eq("clinical_full_name", parsed.full_name, "Dilnoza Karimova")
        runner.eq("clinical_diagnosis", parsed.diagnosis, "Servikal osteoxondroz")

    clinical_result = capture_clinical_form(clinical_text, source="telegram")
    runner.true("clinical_capture", clinical_result is not None)
    if clinical_result:
        runner.check("clinical_records_saved", clinical_result.records_saved >= 3, "")
        records = get_medical_history(clinical_result.patient_id)
        types = {row["record_type"] for row in records}
        runner.check("clinical_symptom_saved", "symptom" in types, repr(types))
        runner.check("clinical_diagnosis_saved", "diagnosis" in types, repr(types))
        runner.check("clinical_treatment_saved", "treatment" in types, repr(types))

    async def run_clinical_capture() -> bool:
        update = FakeUpdate(FakeMessage(text=clinical_text))
        return await handle_admin_chat_text(update, FakeContext())

    clinical_handled = asyncio.run(run_clinical_capture())
    runner.true("telegram_clinical_form", clinical_handled)

    clinical_api = client.post(
        "/api/v1/patients/clinical-form",
        headers={"X-API-Key": "test-intake-key"},
        json={"source": "web", "text": clinical_text},
    )
    runner.eq("clinical_api_status", clinical_api.status_code, 200)
    clinical_body = clinical_api.json()
    runner.eq("clinical_api_name", clinical_body["full_name"], "Dilnoza Karimova")
    runner.check("clinical_api_records", clinical_body["records_saved"] >= 1, clinical_body)

    print()
    print("=" * 72)
    print(f"PHASE 6 VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)

    print("Phase 6 OK: universal patient capture verified")
    print("=" * 72)


if __name__ == "__main__":
    main()

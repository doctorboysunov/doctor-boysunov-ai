"""Phase 9.7: AI Clinic Locator verification."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_9_7.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ADMIN_TELEGRAM_IDS"] = "999001"
os.environ["DASHBOARD_API_KEY"] = "test-clinic-locator-key"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "clinic-locator-test-token")
os.environ.setdefault("OPENAI_API_KEY", "clinic-locator-test-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from fastapi.testclient import TestClient  # noqa: E402

from app.api.clinic_api import app as clinic_app  # noqa: E402
from app.db.connection import get_connection, init_db  # noqa: E402
from app.handlers.appointments import (  # noqa: E402
    BOOKING_STATE_KEY,
    handle_appointment_flow,
    is_booking_trigger,
)
from app.repositories.appointment_repository import create_appointment  # noqa: E402
from app.repositories.clinic_repository import create_clinic_location  # noqa: E402
from app.repositories.conversation_repository import get_or_create_active_conversation  # noqa: E402
from app.repositories.patient_profile_repository import update_patient_profile  # noqa: E402
from app.services.clinic_locator_service import (  # noqa: E402
    format_clinic_recommendation_message,
    get_available_appointment_times,
    haversine_km,
    recommend_clinic_for_patient,
)
from app.services.patient_creation_engine import create_patient_intelligently  # noqa: E402

# Monday — all seeded clinics work mon–fri
TEST_DATE = "2026-07-27"
PATIENT_LAT = 41.2995
PATIENT_LON = 69.2401
API_HEADERS = {"X-API-Key": "test-clinic-locator-key"}


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
    def __init__(self, user_id: int) -> None:
        self.id = user_id
        self.username = "patient"
        self.full_name = "Clinic Locator Patient"


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, user_id: int, text: str) -> None:
        self.effective_user = FakeUser(user_id)
        self.message = FakeMessage(text)


class FakeContext:
    def __init__(self) -> None:
        self.user_data: dict = {}


def _book_all_slots(clinic_id: int, patient_id: int, *, appointment_date: str) -> None:
    from app.repositories.clinic_repository import get_clinic_location

    clinic = get_clinic_location(clinic_id)
    slots = get_available_appointment_times(clinic, appointment_date=appointment_date)
    for slot in slots:
        create_appointment(
            patient_id=patient_id,
            doctor_name=clinic["staff_name"],
            appointment_date=appointment_date,
            appointment_time=slot,
            complaint="slot fill",
            clinic_location_id=clinic_id,
        )


def main() -> None:
    runner = TestRunner()
    init_db()

    runner.check("haversine_zero", haversine_km(PATIENT_LAT, PATIENT_LON, PATIENT_LAT, PATIENT_LON) < 0.01, "")
    runner.check(
        "haversine_positive",
        haversine_km(PATIENT_LAT, PATIENT_LON, 41.35, 69.30) > 5,
        "",
    )

    runner.check("booking_trigger_uz", is_booking_trigger("Navbat olmoqchiman"), "")
    runner.check("booking_trigger_en", is_booking_trigger("I want an appointment please"), "")
    runner.check("booking_trigger_negative", not is_booking_trigger("Salom"), "")

    doctor_near = create_clinic_location(
        clinic_name="Boysunov Clinic",
        staff_name="Sohibnazar Boysunov",
        role="doctor",
        specialty="neurology",
        address="Toshkent, markaz",
        google_maps_link="https://maps.google.com/?q=41.2995,69.2401",
        latitude=PATIENT_LAT,
        longitude=PATIENT_LON,
        phone="+998901111111",
        services="EMG, MRI",
        sort_priority=10,
    )
    student_near = create_clinic_location(
        clinic_name="Boysunov Clinic",
        staff_name="Talaba Ali",
        role="student",
        specialty="neurology",
        address="Toshkent, talaba filiali",
        latitude=41.305,
        longitude=69.245,
        phone="+998902222222",
        services="EMG",
        sort_priority=20,
    )

    created = create_patient_intelligently(
        source="telegram",
        text="Clinic Locator Patient 901777001",
        started_at="2026-07-01",
        telegram_id=720001,
    )
    runner.check("patient_created", created is not None, repr(created))
    if created is None:
        _report(runner)
        return

    patient_id = created.patient_id
    update_patient_profile(
        patient_id,
        phone_number="+998901777001",
        latitude=PATIENT_LAT,
        longitude=PATIENT_LON,
    )

    rec = recommend_clinic_for_patient(
        patient_id,
        specialty="neurology",
        appointment_date=TEST_DATE,
    )
    runner.check("recommend_found", rec is not None, repr(rec))
    if rec:
        runner.eq("prefers_doctor", rec["role"], "doctor")
        runner.eq("prefers_nearest_doctor", rec["staff_name"], "Sohibnazar Boysunov")
        runner.check("has_available_times", len(rec["available_appointment_times"]) > 0, repr(rec))
        runner.check("has_maps_link", "google" in (rec.get("google_maps_link") or ""), "")
        runner.check("has_phone", rec.get("phone") == "+998901111111", repr(rec.get("phone")))
        runner.check(
            "distance_small",
            rec.get("distance_km") is not None and rec["distance_km"] < 1,
            repr(rec.get("distance_km")),
        )
        runner.check("not_fallback", not rec.get("fallback_used"), "")

    slots = get_available_appointment_times(doctor_near, appointment_date=TEST_DATE)
    runner.check("slot_generation", "09:00" in slots and "17:30" in slots, repr(slots[:5]))

    _book_all_slots(doctor_near["id"], patient_id, appointment_date=TEST_DATE)

    fallback_rec = recommend_clinic_for_patient(
        patient_id,
        specialty="neurology",
        appointment_date=TEST_DATE,
    )
    runner.check("fallback_found", fallback_rec is not None, "")
    if fallback_rec:
        runner.eq("fallback_to_student", fallback_rec["role"], "student")
        runner.eq("fallback_staff", fallback_rec["staff_name"], "Talaba Ali")
        runner.true = lambda name, value: runner.check(name, bool(value), repr(value))
        runner.true("fallback_flag", fallback_rec.get("fallback_used"))
        runner.check("student_has_times", len(fallback_rec["available_appointment_times"]) > 0, "")

    create_clinic_location(
        clinic_name="Uzoq filial",
        staff_name="Uzoq Shifokor",
        role="doctor",
        specialty="neurology",
        address="Toshkent, uzoq",
        latitude=41.35,
        longitude=69.30,
        phone="+998903333333",
        sort_priority=30,
    )

    cardio_only = create_clinic_location(
        clinic_name="Kardio markaz",
        staff_name="Kardio Shifokor",
        role="doctor",
        specialty="cardiology",
        address="Toshkent",
        latitude=41.30,
        longitude=69.24,
        sort_priority=5,
    )
    neuro_rec = recommend_clinic_for_patient(
        patient_id,
        specialty="neurology",
        appointment_date=TEST_DATE,
    )
    runner.check(
        "specialty_excludes_cardio",
        neuro_rec is None or neuro_rec["clinic_location_id"] != cardio_only["id"],
        repr(neuro_rec),
    )

    formatted = format_clinic_recommendation_message(fallback_rec or rec or {})
    runner.check("format_has_clinic", "Tavsiya etilgan klinika" in formatted, formatted[:120])
    runner.check("format_has_booking_hint", "Navbat olmoqchiman" in formatted, "")

    client = TestClient(clinic_app)
    runner.eq("api_health", client.get("/api/v1/health").status_code, 200)

    listed = client.get("/api/v1/clinics", headers=API_HEADERS)
    runner.eq("api_list_ok", listed.status_code, 200)
    runner.check("api_list_count", listed.json()["count"] >= 4, repr(listed.json()))

    created_api = client.post(
        "/api/v1/clinics",
        headers=API_HEADERS,
        json={
            "clinic_name": "API Clinic",
            "staff_name": "API Doctor",
            "role": "assistant",
            "address": "API Address",
            "latitude": 41.31,
            "longitude": 69.28,
            "phone": "+998904444444",
        },
    )
    runner.eq("api_create_ok", created_api.status_code, 200)
    api_clinic_id = created_api.json()["clinic"]["id"]

    fetched = client.get(f"/api/v1/clinics/{api_clinic_id}", headers=API_HEADERS)
    runner.eq("api_get_ok", fetched.status_code, 200)
    runner.eq("api_get_name", fetched.json()["staff_name"], "API Doctor")

    updated = client.put(
        f"/api/v1/clinics/{api_clinic_id}",
        headers=API_HEADERS,
        json={"phone": "+998905555555"},
    )
    runner.eq("api_update_ok", updated.status_code, 200)
    runner.eq("api_update_phone", updated.json()["clinic"]["phone"], "+998905555555")

    recommend_api = client.get(
        f"/api/v1/clinics/recommend/{patient_id}",
        headers=API_HEADERS,
        params={"specialty": "neurology", "appointment_date": TEST_DATE},
    )
    runner.eq("api_recommend_ok", recommend_api.status_code, 200)
    runner.check("api_recommend_role", recommend_api.json().get("role") in {"student", "doctor"}, "")

    deleted = client.delete(f"/api/v1/clinics/{api_clinic_id}", headers=API_HEADERS)
    runner.eq("api_delete_ok", deleted.status_code, 200)
    runner.check("api_deleted_inactive", not deleted.json()["clinic"]["is_active"], "")

    runner.eq("api_unauthorized", client.get("/api/v1/clinics").status_code, 401)

    # Booking flow shows clinic recommendation on trigger
    context = FakeContext()
    conversation_id = get_or_create_active_conversation(patient_id)
    trigger_update = FakeUpdate(patient_id, "Navbat olmoqchiman")
    handled = asyncio.run(
        handle_appointment_flow(
            trigger_update,
            context,
            user_id=patient_id,
            conversation_id=conversation_id,
        )
    )
    runner.check("booking_trigger_handled", handled, "")
    booking = context.user_data.get(BOOKING_STATE_KEY)
    runner.check("booking_state_started", booking is not None, "")
    if booking:
        runner.check("booking_has_clinic_id", booking.get("clinic_location_id") is not None, repr(booking))
        runner.check("booking_has_doctor", booking.get("doctor_name") is not None, repr(booking))
    runner.check(
        "booking_shows_recommendation",
        trigger_update.message.reply_text.await_count >= 2,
        str(trigger_update.message.reply_text.await_count),
    )
    second_reply = trigger_update.message.reply_text.await_args_list[1].args[0]
    runner.check("booking_reply_has_address", "📍" in second_reply or "Tavsiya" in second_reply, second_reply[:100])

    with get_connection() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        appointment_columns = {row[1] for row in conn.execute("PRAGMA table_info(appointments)").fetchall()}
    runner.check("clinic_locations_table", "clinic_locations" in tables, repr(tables))
    runner.check("appointments_clinic_fk", "clinic_location_id" in appointment_columns, "")

    _report(runner)


def _report(runner: TestRunner) -> None:
    print()
    print("=" * 72)
    print(f"PHASE 9.7 AI CLINIC LOCATOR: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Phase 9.7 OK: AI Clinic Locator verified")
    print("=" * 72)


if __name__ == "__main__":
    main()

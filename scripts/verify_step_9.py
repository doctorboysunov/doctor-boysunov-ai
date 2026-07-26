"""Phase 9: Electronic Medical Record (EMR) verification."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_9.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["EMR_API_KEY"] = "test-emr-key"
os.environ["DASHBOARD_API_KEY"] = "test-emr-key"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "emr-test-token")
os.environ.setdefault("OPENAI_API_KEY", "emr-test-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from fastapi.testclient import TestClient  # noqa: E402

from app.api.emr_api import app as emr_app  # noqa: E402
from app.db.connection import get_connection, init_db  # noqa: E402
from app.repositories.appointment_repository import create_appointment  # noqa: E402
from app.repositories.emr_repository import (  # noqa: E402
    count_emr_visits_for_patient,
    get_emr_visit,
    list_emr_visits_for_patient,
)
from app.services.dashboard_actions import action_open_patient_card  # noqa: E402
from app.services.emr_service import (  # noqa: E402
    build_patient_emr,
    build_patient_timeline,
    create_visit,
    edit_visit,
    get_visit_history,
)
from app.services.patient_creation_engine import create_patient_intelligently  # noqa: E402


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


API_HEADERS = {"X-API-Key": "test-emr-key"}


def main() -> None:
    runner = TestRunner()
    init_db()
    today = date.today().isoformat()

    with get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    runner.check("emr_visits_table", "emr_visits" in tables, str(sorted(tables)))

    created = create_patient_intelligently(
        source="telegram",
        text="EMR Test Patient 901555001",
        started_at=today,
    )
    runner.check("patient_created", created is not None, repr(created))
    if created is None:
        _report(runner)
        return

    patient_id = created.patient_id
    runner.eq("initial_visit_count", count_emr_visits_for_patient(patient_id), 1)

    initial_visits = list_emr_visits_for_patient(patient_id)
    runner.check("initial_visit_exists", len(initial_visits) == 1, str(initial_visits))
    if initial_visits:
        runner.eq("initial_visit_date", initial_visits[0]["visit_date"], today)
        runner.check(
            "initial_visit_notes",
            "Initial registration" in (initial_visits[0].get("notes") or ""),
            initial_visits[0].get("notes"),
        )

    visit2 = create_visit(
        patient_id,
        visit_date=today,
        main_complaint="Bosh og'rig'i va ko'krak qisishishi",
        examination_findings="Holati o'rtacha og'ir",
        neurological_examination="Kranial nervlar normal",
        preliminary_diagnosis="Migren?",
        final_diagnosis="Tension-type headache",
        icd10_code="G44.2",
        recommended_examinations="MRI bosh miya",
        treatment_plan="Analgetiklar, dam olish",
        procedures_performed="EKG",
        follow_up_schedule="2 hafta",
        notes="Birinchi to'liq ko'rik",
    )
    runner.eq("second_visit_id", visit2["id"], 2)
    runner.eq("visit_complaint", visit2["main_complaint"], "Bosh og'rig'i va ko'krak qisishishi")
    runner.eq("visit_icd10", visit2["icd10_code"], "G44.2")

    visit3 = create_visit(
        patient_id,
        visit_date="2026-02-01",
        main_complaint="Qayta murojaat — yengillashgan",
        final_diagnosis="Yaxshilanish",
        treatment_plan="Davom ettirish",
    )
    runner.eq("third_visit_id", visit3["id"], 3)
    runner.eq("unlimited_visits", count_emr_visits_for_patient(patient_id), 3)

    edited = edit_visit(
        patient_id,
        visit2["id"],
        final_diagnosis="Tension-type headache (confirmed)",
        notes="Updated after labs",
    )
    runner.check("edit_visit", edited is not None, repr(edited))
    if edited:
        runner.eq(
            "edited_final_diagnosis",
            edited["final_diagnosis"],
            "Tension-type headache (confirmed)",
        )
        runner.check("edited_notes", "Updated after labs" in edited["notes"], edited["notes"])

    stored = get_emr_visit(visit2["id"])
    runner.check("persisted_edit", stored is not None and stored["final_diagnosis"] == edited["final_diagnosis"], "")

    history = get_visit_history(patient_id)
    runner.eq("history_visit_count", history["visit_count"], 3)
    runner.check("previous_complaints", len(history["previous_complaints"]) >= 2, str(history["previous_complaints"]))
    runner.check("previous_diagnoses", len(history["previous_diagnoses"]) >= 2, str(history["previous_diagnoses"]))
    runner.check("previous_treatments", len(history["previous_treatments"]) >= 2, str(history["previous_treatments"]))
    runner.check("previous_follow_ups", len(history["previous_follow_ups"]) >= 6, str(len(history["previous_follow_ups"])))

    create_appointment(
        patient_id=patient_id,
        doctor_name="Dr. Boysunov",
        appointment_date=today,
        appointment_time="10:00",
        complaint="Follow-up appointment",
    )

    timeline = build_patient_timeline(patient_id)
    runner.check("timeline_events", timeline["event_count"] >= 5, str(timeline["event_count"]))
    event_types = {event["event_type"] for event in timeline["timeline"]}
    runner.check("timeline_has_visit", "visit" in event_types, str(event_types))
    runner.check("timeline_has_follow_up", "follow_up" in event_types, str(event_types))
    runner.check("timeline_has_appointment", "appointment" in event_types, str(event_types))

    dates = [event["event_date"] for event in timeline["timeline"]]
    runner.check("timeline_sorted_desc", dates == sorted(dates, reverse=True), str(dates[:5]))

    emr = build_patient_emr(patient_id)
    runner.eq("emr_patient_id", emr["patient_id"], patient_id)
    runner.check("emr_has_visits", len(emr["emr"]["visits"]) == 3, str(len(emr["emr"]["visits"])))
    runner.check("emr_has_timeline", len(emr["emr"]["timeline"]) >= 5, str(len(emr["emr"]["timeline"])))
    runner.check("emr_has_complaints", len(emr["emr"]["previous_complaints"]) >= 2, "")
    runner.check("emr_has_diagnoses", len(emr["emr"]["previous_diagnoses"]) >= 2, "")

    import asyncio

    card = asyncio.run(action_open_patient_card(patient_id))
    runner.check("dashboard_card_has_emr", "emr" in card, str(card.keys()))
    runner.eq("dashboard_card_visit_count", card["emr"]["visit_count"], 3)

    client = TestClient(emr_app)
    health = client.get("/api/v1/health")
    runner.eq("api_health", health.status_code, 200)

    unauthorized = client.get(f"/api/v1/emr/patient/{patient_id}")
    runner.eq("api_requires_key", unauthorized.status_code, 401)

    full = client.get(f"/api/v1/emr/patient/{patient_id}", headers=API_HEADERS)
    runner.eq("api_get_emr", full.status_code, 200)
    runner.eq("api_emr_visits", full.json()["emr"]["visit_count"], 3)

    hist_resp = client.get(f"/api/v1/emr/patient/{patient_id}/history", headers=API_HEADERS)
    runner.eq("api_history", hist_resp.status_code, 200)
    runner.eq("api_history_count", hist_resp.json()["visit_count"], 3)

    timeline_resp = client.get(f"/api/v1/emr/patient/{patient_id}/timeline", headers=API_HEADERS)
    runner.eq("api_timeline", timeline_resp.status_code, 200)
    runner.check("api_timeline_events", timeline_resp.json()["event_count"] >= 5, "")

    create_resp = client.post(
        f"/api/v1/emr/patient/{patient_id}/visits",
        headers=API_HEADERS,
        json={
            "visit_date": "2026-03-15",
            "main_complaint": "API visit",
            "final_diagnosis": "Stable",
        },
    )
    runner.eq("api_create_visit", create_resp.status_code, 200)
    runner.check("api_create_success", create_resp.json()["success"] is True, create_resp.text)
    runner.eq("unlimited_after_api", count_emr_visits_for_patient(patient_id), 4)

    new_visit_id = create_resp.json()["visit"]["id"]
    update_resp = client.put(
        f"/api/v1/emr/patient/{patient_id}/visits/{new_visit_id}",
        headers=API_HEADERS,
        json={"notes": "Edited via API", "icd10_code": "Z00.0"},
    )
    runner.eq("api_edit_visit", update_resp.status_code, 200)
    runner.eq("api_edit_icd10", update_resp.json()["visit"]["icd10_code"], "Z00.0")

    missing = client.get("/api/v1/emr/patient/999999", headers=API_HEADERS)
    runner.eq("api_patient_not_found", missing.status_code, 404)

    bad_edit = client.put(
        f"/api/v1/emr/patient/{patient_id}/visits/999999",
        headers=API_HEADERS,
        json={"notes": "nope"},
    )
    runner.eq("api_visit_not_found", bad_edit.status_code, 404)

    init_db()
    runner.eq("emr_persists_after_reinit", count_emr_visits_for_patient(patient_id), 4)

    _report(runner)


def _report(runner: TestRunner) -> None:
    print()
    print("=" * 72)
    print(f"PHASE 9 EMR VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Phase 9 OK: Electronic Medical Record verified")
    print("=" * 72)


if __name__ == "__main__":
    main()

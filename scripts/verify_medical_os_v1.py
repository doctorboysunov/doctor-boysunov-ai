"""Medical OS V1 — platform foundation verification."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / f"verify_medical_os_v1_{int(time.time())}.db"

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("OPENAI_API_KEY", "medical-os-test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "medical-os-test")
os.environ.setdefault("DASHBOARD_API_KEY", "test-api-key")
os.environ["ADMIN_TELEGRAM_IDS"] = ""

sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient  # noqa: E402

from app.api.platform_api import app  # noqa: E402
from app.db.connection import get_connection, init_db  # noqa: E402
from app.medical_brain.contract import CONTRACT_VERSION, PIPELINE_STEPS  # noqa: E402
from app.services.emr_ai_service import get_ai_assessment, list_pending_reviews, review_visit, save_ai_assessment  # noqa: E402
from app.services.emr_service import create_visit  # noqa: E402

HEADERS = {"X-API-Key": os.environ.get("DASHBOARD_API_KEY", "test-api-key")}


class Runner:
    def __init__(self) -> None:
        self.passed = 0
        self.failed: list[tuple[str, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.passed += 1
        else:
            self.failed.append((name, detail or "failed"))

    @property
    def total(self) -> int:
        return self.passed + len(self.failed)


def _seed_patient(patient_id: int = 1) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, telegram_id, created_at) VALUES (?, ?, datetime('now'))",
            (patient_id, 900001),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO patient_profiles
            (user_id, full_name, phone_number, created_at, updated_at)
            VALUES (?, ?, ?, datetime('now'), datetime('now'))
            """,
            (patient_id, "Test Patient", "+998901234567"),
        )
        conn.commit()


def main() -> None:
    runner = Runner()
    _seed_patient()

    # M1: Architecture contracts
    runner.check("brain_contract_version", CONTRACT_VERSION == "1.1.0")
    runner.check("brain_pipeline_steps", len(PIPELINE_STEPS) >= 10)

    client = TestClient(app)
    health = client.get("/api/v1/health", headers=HEADERS)
    runner.check("platform_api_health", health.status_code == 200 and health.json()["platform"] == "medical-os")

    info = client.get("/api/v1/platform/info", headers=HEADERS)
    runner.check("platform_info", "medical_brain" in info.json().get("modules", []))

    # M3: EMR AI assessment workflow
    visit = create_visit(1, visit_date="2026-07-26", main_complaint="Bosh og'rig'i")
    visit_id = visit["id"]

    saved = save_ai_assessment(
        visit_id,
        doctor_emr={
            "chief_complaint": "Bosh og'rig'i",
            "differential_diagnoses": ["Migren", "Tension headache"],
            "red_flags_noted": [],
            "urgency": "routine",
            "recommended_investigations": ["Neurologist exam"],
        },
        medical_brain={
            "step1_patient_meaning": "Bosh og'riq shikoyati",
            "step3_hypotheses": [{"name": "Migren", "probability": "high", "rationale": "Pulsating"}],
            "step6_next_question_rationale": "Onset pattern needed",
        },
        primary_specialty="neurology",
        secondary_specialties=[],
    )
    runner.check("ai_assessment_saved", saved["ai_review_status"] == "draft")
    runner.check("ai_assessment_json", bool(saved.get("ai_assessment_json")))

    assessment = get_ai_assessment(visit_id)
    runner.check("ai_assessment_retrieved", assessment is not None and assessment["doctor_emr"]["chief_complaint"] == "Bosh og'rig'i")

    pending = list_pending_reviews()
    runner.check("pending_reviews_list", any(v["id"] == visit_id for v in pending))

    reviewed = review_visit(
        visit_id,
        doctor_id="dr_test",
        final_diagnosis="Migren",
        treatment_plan="Rest, hydration",
        approve=True,
    )
    runner.check("visit_reviewed", reviewed["ai_review_status"] == "reviewed")
    runner.check("doctor_signed", reviewed["doctor_reviewed_by"] == "dr_test")

    # M5: Platform API endpoints
    pending_api = client.get("/api/v1/emr/reviews/pending", headers=HEADERS)
    runner.check("api_pending_reviews", pending_api.status_code == 200)

    assessment_api = client.get(f"/api/v1/emr/visits/{visit_id}/ai-assessment", headers=HEADERS)
    runner.check("api_get_assessment", assessment_api.status_code == 200)

    review_api = client.post(
        f"/api/v1/emr/visits/{visit_id}/review",
        headers=HEADERS,
        json={"doctor_id": "dr_api", "notes": "Reviewed via API", "approve": True},
    )
    runner.check("api_review_visit", review_api.status_code == 200)

    dashboard_api = client.get("/api/v1/dashboard?period=today", headers=HEADERS)
    runner.check("api_dashboard", dashboard_api.status_code == 200)

    # M2: Medical Brain delegation (mock GPT)
    from app.services.consultation_ai import run_medical_turn  # noqa: E402
    from app.medical_brain.types import MedicalBrainInternal, MedicalBrainOutput  # noqa: E402
    from app.clinical_brain.types import DoctorEmrUpdate  # noqa: E402

    mock_output = MedicalBrainOutput(
        patient_reply="Tushundim. Qachondan boshlab?",
        doctor_emr=DoctorEmrUpdate(chief_complaint="Test"),
        internal=MedicalBrainInternal(step1_patient_meaning="test"),
        primary_specialty="neurology",
    )
    with patch("app.services.consultation_ai.run_medical_brain", return_value=mock_output):
        turn = run_medical_turn(
            user_message="Boshim og'riyapti",
            session_messages=[{"role": "user", "content": "Boshim og'riyapti"}],
            known_facts={},
            topics_covered=[],
            prior_complaints=[],
        )
    runner.check("medical_turn_delegates", "Qachondan" in turn.patient_reply)
    runner.check("medical_turn_specialty", turn.primary_specialty == "neurology")

    # Dashboard static
    dash_page = client.get("/dashboard/")
    runner.check("dashboard_served", dash_page.status_code == 200)

    print(f"\n=== Medical OS V1 Platform: {runner.passed}/{runner.total} passed ===")
    for name, detail in runner.failed:
        print(f"FAIL: {name} — {detail}")
    if runner.failed:
        sys.exit(1)
    print("PASS: Medical OS V1 foundation verified")


if __name__ == "__main__":
    main()

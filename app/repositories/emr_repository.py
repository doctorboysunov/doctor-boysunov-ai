"""EMR visit persistence — one lifelong record per patient, unlimited visits."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection
from app.domain.emr import EMR_V1_FIELDS, EMR_VISIT_FIELDS

logger = logging.getLogger("doctor_boysunov.emr")

_EMR_VISIT_COLUMNS = (
    "id",
    "patient_id",
    *EMR_VISIT_FIELDS,
    *EMR_V1_FIELDS,
    "created_at",
    "updated_at",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_visit(row) -> dict[str, Any]:
    keys = row.keys()
    visit = {column: row[column] if column in keys else None for column in _EMR_VISIT_COLUMNS}
    visit["id"] = int(visit["id"])
    visit["patient_id"] = int(visit["patient_id"])
    return visit


def _patient_exists(patient_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE id = ?",
            (patient_id,),
        ).fetchone()
    return row is not None


def create_emr_visit(
    patient_id: int,
    *,
    visit_date: str,
    main_complaint: str | None = None,
    examination_findings: str | None = None,
    neurological_examination: str | None = None,
    preliminary_diagnosis: str | None = None,
    final_diagnosis: str | None = None,
    icd10_code: str | None = None,
    recommended_examinations: str | None = None,
    treatment_plan: str | None = None,
    procedures_performed: str | None = None,
    follow_up_schedule: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    if not _patient_exists(patient_id):
        raise ValueError(f"Patient not found: {patient_id}")

    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO emr_visits (
                patient_id, visit_date, main_complaint, examination_findings,
                neurological_examination, preliminary_diagnosis, final_diagnosis,
                icd10_code, recommended_examinations, treatment_plan,
                procedures_performed, follow_up_schedule, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                visit_date,
                main_complaint,
                examination_findings,
                neurological_examination,
                preliminary_diagnosis,
                final_diagnosis,
                icd10_code,
                recommended_examinations,
                treatment_plan,
                procedures_performed,
                follow_up_schedule,
                notes,
                now,
                now,
            ),
        )
        visit_id = int(cursor.lastrowid)
        row = conn.execute(
            "SELECT * FROM emr_visits WHERE id = ?",
            (visit_id,),
        ).fetchone()
        conn.commit()

    visit = _row_to_visit(row)
    logger.info("emr_visit_created patient_id=%s visit_id=%s", patient_id, visit_id)
    return visit


def get_emr_visit(visit_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM emr_visits WHERE id = ?",
            (visit_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_visit(row)


def update_emr_visit(
    visit_id: int,
    *,
    visit_date: str | None = None,
    main_complaint: str | None = None,
    examination_findings: str | None = None,
    neurological_examination: str | None = None,
    preliminary_diagnosis: str | None = None,
    final_diagnosis: str | None = None,
    icd10_code: str | None = None,
    recommended_examinations: str | None = None,
    treatment_plan: str | None = None,
    procedures_performed: str | None = None,
    follow_up_schedule: str | None = None,
    notes: str | None = None,
    ai_assessment_json: str | None = None,
    ai_review_status: str | None = None,
    doctor_reviewed_at: str | None = None,
    doctor_reviewed_by: str | None = None,
    urgency: str | None = None,
    primary_specialty: str | None = None,
    secondary_specialties_json: str | None = None,
) -> dict[str, Any] | None:
    existing = get_emr_visit(visit_id)
    if existing is None:
        return None

    updates: dict[str, Any] = {}
    for field, value in (
        ("visit_date", visit_date),
        ("main_complaint", main_complaint),
        ("examination_findings", examination_findings),
        ("neurological_examination", neurological_examination),
        ("preliminary_diagnosis", preliminary_diagnosis),
        ("final_diagnosis", final_diagnosis),
        ("icd10_code", icd10_code),
        ("recommended_examinations", recommended_examinations),
        ("treatment_plan", treatment_plan),
        ("procedures_performed", procedures_performed),
        ("follow_up_schedule", follow_up_schedule),
        ("notes", notes),
        ("ai_assessment_json", ai_assessment_json),
        ("ai_review_status", ai_review_status),
        ("doctor_reviewed_at", doctor_reviewed_at),
        ("doctor_reviewed_by", doctor_reviewed_by),
        ("urgency", urgency),
        ("primary_specialty", primary_specialty),
        ("secondary_specialties_json", secondary_specialties_json),
    ):
        if value is not None:
            updates[field] = value

    if not updates:
        return existing

    updates["updated_at"] = _utc_now()
    set_clause = ", ".join(f"{column} = ?" for column in updates)
    params = list(updates.values()) + [visit_id]

    with get_connection() as conn:
        conn.execute(
            f"UPDATE emr_visits SET {set_clause} WHERE id = ?",
            params,
        )
        row = conn.execute(
            "SELECT * FROM emr_visits WHERE id = ?",
            (visit_id,),
        ).fetchone()
        conn.commit()

    visit = _row_to_visit(row)
    logger.info("emr_visit_updated visit_id=%s patient_id=%s", visit_id, visit["patient_id"])
    return visit


def list_emr_visits_for_patient(patient_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM emr_visits
            WHERE patient_id = ?
            ORDER BY visit_date DESC, id DESC
            """,
            (patient_id,),
        ).fetchall()
    return [_row_to_visit(row) for row in rows]


def count_emr_visits_for_patient(patient_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM emr_visits WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()
    return int(row["total"])


def list_visits_pending_ai_review(*, limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT v.*, p.full_name, p.phone_number
            FROM emr_visits v
            LEFT JOIN patient_profiles p ON p.user_id = v.patient_id
            WHERE v.ai_review_status = 'draft'
            ORDER BY v.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        visit = _row_to_visit(row)
        visit["patient_name"] = row["full_name"]
        visit["patient_phone"] = row["phone_number"]
        results.append(visit)
    return results


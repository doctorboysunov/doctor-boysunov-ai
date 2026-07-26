"""Persistence for professional medical consultation sessions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_connection
from app.domain.consultation import ComplaintCategory, ConsultationPhase, ConsultationSession


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_active_session(patient_id: int) -> ConsultationSession | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM consultation_sessions
            WHERE patient_id = ? AND phase IN (
                'collecting',
                'awaiting_help_choice',
                'awaiting_session_choice',
                'awaiting_complaint_clarification'
            )
            ORDER BY id DESC
            LIMIT 1
            """,
            (patient_id,),
        ).fetchone()
    if row is None:
        return None
    return ConsultationSession.from_row(dict(row))


def get_session_by_id(session_id: int) -> ConsultationSession | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM consultation_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return ConsultationSession.from_row(dict(row))


def create_session(
    patient_id: int,
    visit_id: int,
    complaint_category: ComplaintCategory,
    *,
    current_question_id: str | None = None,
) -> ConsultationSession:
    now = _now_iso()
    asked: list[str] = []
    if current_question_id:
        asked = [current_question_id]
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO consultation_sessions (
                patient_id, visit_id, complaint_category, phase,
                asked_question_ids, answers_json, current_question_id,
                summary_json, created_at, updated_at
            ) VALUES (?, ?, ?, 'collecting', ?, '{}', ?, NULL, ?, ?)
            """,
            (
                patient_id,
                visit_id,
                complaint_category,
                json.dumps(asked, ensure_ascii=False),
                current_question_id,
                now,
                now,
            ),
        )
        session_id = int(cursor.lastrowid)
        conn.commit()
    session = get_session_by_id(session_id)
    if session is None:
        raise RuntimeError("Failed to create consultation session")
    return session


def update_session(
    session_id: int,
    *,
    phase: ConsultationPhase | None = None,
    asked_question_ids: list[str] | None = None,
    answers: dict[str, str] | None = None,
    current_question_id: str | None = None,
    clear_current_question: bool = False,
    summary: dict[str, Any] | None = None,
) -> ConsultationSession:
    session = get_session_by_id(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")

    new_phase = phase or session.phase
    new_asked = asked_question_ids if asked_question_ids is not None else session.asked_question_ids
    new_answers = answers if answers is not None else session.answers
    if clear_current_question:
        new_current: str | None = None
    elif current_question_id is not None:
        new_current = current_question_id
    else:
        new_current = session.current_question_id

    new_summary = summary if summary is not None else session.summary

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE consultation_sessions
            SET phase = ?,
                asked_question_ids = ?,
                answers_json = ?,
                current_question_id = ?,
                summary_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                new_phase,
                json.dumps(new_asked, ensure_ascii=False),
                json.dumps(new_answers, ensure_ascii=False),
                new_current,
                json.dumps(new_summary, ensure_ascii=False) if new_summary else None,
                _now_iso(),
                session_id,
            ),
        )
        conn.commit()

    updated = get_session_by_id(session_id)
    if updated is None:
        raise RuntimeError("Failed to update consultation session")
    return updated

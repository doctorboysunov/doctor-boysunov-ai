#!/usr/bin/env python3
"""Phase 1 Step 2 — clean architecture skeleton verification."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import BOT_TOKEN, OPENAI_API_KEY, DATABASE_PATH
from app.domain.entities import Appointment, Conversation, Message, PatientMemory, User
from app.domain.repositories import (
    AppointmentRepository,
    ConversationRepository,
    MemoryRepository,
    UserRepository,
)
from app.infrastructure import get_connection, init_db
from app.settings import get_settings


def main() -> int:
    settings = get_settings()
    assert settings.telegram_bot_token == BOT_TOKEN
    assert settings.openai_api_key == OPENAI_API_KEY
    assert settings.database_path == DATABASE_PATH

    # Entities instantiate
    _ = User(id=1, telegram_id=123, full_name="Test")
    _ = Conversation(id=1, user_id=1)
    _ = Message(id=1, conversation_id=1, role="user", content="Salom")
    _ = Appointment(
        id=1,
        patient_id=1,
        doctor_name="Dr. Boysunov",
        appointment_date="2026-07-26",
        appointment_time="10:00",
        complaint="checkup",
    )
    _ = PatientMemory(user_id=1, key="allergy", value="penicillin")

    # Protocols are importable (structural typing — no runtime isinstance needed)
    assert UserRepository.__name__ == "UserRepository"
    assert ConversationRepository.__name__ == "ConversationRepository"
    assert AppointmentRepository.__name__ == "AppointmentRepository"
    assert MemoryRepository.__name__ == "MemoryRepository"

    # Infrastructure re-exports work
    init_db()
    with get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "users" in tables
    assert "messages" in tables

    # Existing handlers still importable (bot not broken)
    from app.handlers import chat, start  # noqa: F401

    print("Phase 1 Step 2 OK: domain entities, repository protocols, application/infrastructure skeleton")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

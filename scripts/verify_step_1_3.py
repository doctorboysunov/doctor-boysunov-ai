#!/usr/bin/env python3
"""Phase 1 Step 3 — dependency injection and use-case wiring verification."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_1_3.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "verify-step-1-3-token")
os.environ.setdefault("OPENAI_API_KEY", "verify-step-1-3-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.application.chat import SendMessageResult, send_patient_message  # noqa: E402
from app.container import AppContainer, bootstrap, build_container, get_container  # noqa: E402
from app.db.connection import get_connection  # noqa: E402
from app.domain.repositories import (  # noqa: E402
    AppointmentRepository,
    ConversationRepository,
    MemoryRepository,
    UserRepository,
)
from app.infrastructure.repositories import (  # noqa: E402
    SqliteAppointmentRepository,
    SqliteConversationRepository,
    SqliteMemoryRepository,
    SqliteUserIdentityRepository,
    SqliteUserRepository,
)


def main() -> int:
    get_container.cache_clear()

    container = bootstrap()
    assert isinstance(container, AppContainer)
    assert isinstance(container.users, SqliteUserRepository)
    assert isinstance(container.identities, SqliteUserIdentityRepository)
    assert isinstance(container.conversations, SqliteConversationRepository)
    assert isinstance(container.appointments, SqliteAppointmentRepository)
    assert isinstance(container.memories, SqliteMemoryRepository)

    # Structural typing — adapters satisfy domain protocols
    _: UserRepository = container.users
    _: ConversationRepository = container.conversations
    _: AppointmentRepository = container.appointments
    _: MemoryRepository = container.memories

    assert get_container() is container

    user_id = container.users.upsert_telegram_user(
        900001,
        username="step13",
        full_name="Step Three",
    )
    assert user_id > 0

    user = container.users.get_by_telegram_id(900001)
    assert user is not None
    assert user.full_name == "Step Three"

    conversation_id = container.conversations.get_or_create_active_conversation(user_id)
    container.conversations.save_message(conversation_id, "user", "Salom")
    messages = container.conversations.get_last_messages(conversation_id, limit=5)
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "Salom"

    container.memories.upsert_memory(user_id, "allergies", "penicillin")
    memories = container.memories.get_memories(user_id)
    assert any(m.key == "allergies" and m.value == "penicillin" for m in memories)

    appt_id = container.appointments.create_appointment(
        patient_id=user_id,
        doctor_name="Dr. Boysunov",
        appointment_date="2026-07-27",
        appointment_time="10:00",
        complaint="checkup",
    )
    assert appt_id > 0
    appts = container.appointments.get_patient_appointments(user_id)
    assert len(appts) == 1
    assert appts[0].complaint == "checkup"

    with patch("app.application.chat.send_message.ask_ai", return_value="Javob"):
        result = send_patient_message(
            user_id=user_id,
            user_message="Qanday yordam bera olasiz?",
            patient_profile={"full_name": "Step Three"},
        )
    assert isinstance(result, SendMessageResult)
    assert result.reply == "Javob"
    assert result.conversation_id == conversation_id

    with get_connection() as conn:
        msg_count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()[0]
    assert msg_count >= 3  # user + use-case user + assistant

    # main.py entrypoint still imports
    from app.main import main  # noqa: F401

    # Fresh build_container() produces independent instances
    other = build_container()
    assert other is not container

    print(
        "Phase 1 Step 3 OK: container bootstrap, SQLite adapters, send_patient_message use case"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

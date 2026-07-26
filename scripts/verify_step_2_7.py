#!/usr/bin/env python3
"""Phase 2 Step 2.7 — long-term patient_memories verification."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_2_7.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "verify-step-2-7-token")
os.environ.setdefault("OPENAI_API_KEY", "verify-step-2-7-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.container import bootstrap, get_container  # noqa: E402
from app.db.connection import get_connection  # noqa: E402
from app.repositories import memory_repository as legacy_memory_repo  # noqa: E402


def main() -> int:
    get_container.cache_clear()
    bootstrap()

    with get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "patient_memories" in tables

    container = get_container()
    user_id = container.users.upsert_telegram_user(710001, full_name="Memory Test")

    container.memories.upsert_memory(user_id, "preferred_language", "uz")
    container.memories.upsert_memory(user_id, "allergies", "penicillin")
    container.memories.upsert_memory(user_id, "main_concern", "chronic headache")

    memories = container.memories.get_memories(user_id)
    keys = {memory.key for memory in memories}
    assert "preferred_language" in keys
    assert "allergies" in keys
    assert "main_concern" in keys

    stored = legacy_memory_repo.get_memory(user_id, "main_concern")
    assert stored is not None
    assert stored["value"] == "chronic headache"

    # Profile field sync
    allergy_memory = legacy_memory_repo.get_memory(user_id, "allergies")
    assert allergy_memory is not None

    get_container.cache_clear()
    bootstrap()
    reloaded = get_container().memories.get_memories(user_id)
    reloaded_map = {item.key: item.value for item in reloaded}
    assert reloaded_map["preferred_language"] == "uz"
    assert reloaded_map["main_concern"] == "chronic headache"

    container.memories.delete_memory(user_id, "main_concern")
    assert legacy_memory_repo.get_memory(user_id, "main_concern") is None

    print("Phase 2 Step 2.7 OK: patient_memories table, CRUD, restart persistence, profile sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

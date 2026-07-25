"""Step 3.4: permanent medical history separate from patient profile."""

import os
from pathlib import Path

os.environ["DATABASE_PATH"] = "data/test_step_3_4.db"

from app.db.connection import get_connection, init_db
from app.domain.medical_history_types import MEDICAL_RECORD_TYPES
from app.repositories.conversation_repository import upsert_user
from app.repositories.medical_history_repository import (
    add_medical_record,
    count_medical_records,
    get_medical_history,
    get_medical_history_counts,
)
from app.repositories.patient_profile_repository import (
    get_or_create_patient_profile,
    update_patient_profile,
)
from app.settings import get_settings

TEST_DB = Path("data/test_step_3_4.db")

if TEST_DB.exists():
    TEST_DB.unlink()

init_db()

with get_connection() as conn:
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    profile_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(patient_profiles)").fetchall()
    }

assert "medical_history" in tables
assert "symptom" not in profile_columns
assert "diagnosis" not in profile_columns

user_a = upsert_user(telegram_id=880001, username="patient_a", full_name="Patient A")
user_b = upsert_user(telegram_id=880002, username="patient_b", full_name="Patient B")

profile = get_or_create_patient_profile(user_a)
update_patient_profile(user_a, full_name="Dilnoza", age=32)

samples = {
    "symptom": "Bosh og'rig'i va bel og'rig'i",
    "diagnosis": "Lumbal disk herniya",
    "mri": "L4-L5 disk protruziyasi",
    "ct": "L3-L4 darajada degenerativ o'zgarishlar",
    "emg": "Pastki oyoq periferik nerv conduction sekin",
    "laboratory": "Qon biokimyosi: CRP 12 mg/L",
    "treatment": "NSAID va fizioterapiya kursi",
    "consultation": "2026-01-10 nevrolog Dr. Karimov",
}

for record_type, content in samples.items():
    record = add_medical_record(
        user_a,
        record_type,
        content,
        event_date="2026-01-15",
        notes="Test entry",
    )
    assert record["record_type"] == record_type
    assert record["content"] == content
    assert record["user_id"] == user_a

history = get_medical_history(user_a)
assert len(history) == len(MEDICAL_RECORD_TYPES)
assert [row["record_type"] for row in history] == list(MEDICAL_RECORD_TYPES)

mri_only = get_medical_history(user_a, record_type="mri")
assert len(mri_only) == 1
assert mri_only[0]["content"] == samples["mri"]

counts = get_medical_history_counts(user_a)
assert all(counts[record_type] == 1 for record_type in MEDICAL_RECORD_TYPES)

add_medical_record(user_a, "symptom", "Qo'lni uyuqtirish")
assert count_medical_records(user_a, record_type="symptom") == 2

add_medical_record(user_b, "diagnosis", "Gipertoniya")
assert count_medical_records(user_b) == 1
assert count_medical_records(user_a) == len(MEDICAL_RECORD_TYPES) + 1

profile_after = get_or_create_patient_profile(user_a)
assert profile_after["full_name"] == "Dilnoza"
assert profile_after["age"] == 32
assert "symptom" not in profile_after

with get_connection() as conn:
    message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
assert message_count == 0

get_settings.cache_clear()
init_db()

history_after_restart = get_medical_history(user_a)
assert len(history_after_restart) == len(MEDICAL_RECORD_TYPES) + 1
assert history_after_restart[0]["content"] == samples["symptom"]
assert history_after_restart[-1]["content"] == "Qo'lni uyuqtirish"

# Legacy DB migration: add medical_history to DB that only had profile tables.
legacy_db = Path("data/test_step_3_4_legacy.db")
if legacy_db.exists():
    legacy_db.unlink()

import sqlite3

legacy_conn = sqlite3.connect(legacy_db)
legacy_conn.executescript(
    """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        telegram_id INTEGER UNIQUE,
        username TEXT,
        full_name TEXT,
        created_at TEXT
    );
    CREATE TABLE patient_profiles (
        id INTEGER PRIMARY KEY,
        user_id INTEGER UNIQUE,
        full_name TEXT,
        age INTEGER,
        created_at TEXT,
        updated_at TEXT
    );
    """
)
legacy_conn.commit()
legacy_conn.close()

os.environ["DATABASE_PATH"] = str(legacy_db)
from importlib import reload
import app.db.connection as db_connection

reload(db_connection)
db_connection.init_db()

with db_connection.get_connection() as conn:
    legacy_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

assert "medical_history" in legacy_tables

print("Step 3.4 OK: medical history stored separately, all record types, restart persistence")

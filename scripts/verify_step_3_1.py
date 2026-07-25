"""Step 3.1: permanent patient profile table and repository."""

import os
from pathlib import Path

os.environ["DATABASE_PATH"] = "data/test_step_3_1.db"

from app.db.connection import get_connection, init_db
from app.handlers.common import register_telegram_user
from app.repositories.conversation_repository import upsert_user
from app.repositories.patient_profile_repository import (
    get_or_create_patient_profile,
    get_patient_profile,
    update_patient_profile,
)

TEST_DB = Path("data/test_step_3_1.db")


class FakeTelegramUser:
    id = 555001
    username = "patient_test"
    full_name = "Telegram Display Name"


class FakeUpdate:
    effective_user = FakeTelegramUser()


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

assert "patient_profiles" in tables

user_id = upsert_user(
    telegram_id=FakeTelegramUser.id,
    username=FakeTelegramUser.username,
    full_name=FakeTelegramUser.full_name,
)

profile = get_or_create_patient_profile(user_id)
assert profile["user_id"] == user_id
assert profile["full_name"] is None
assert profile["age"] is None
assert profile["sex"] is None
assert profile["phone_number"] is None
assert profile["city_region"] is None
assert profile["occupation"] is None

same_profile = get_or_create_patient_profile(user_id)
assert same_profile["id"] == profile["id"]

updated = update_patient_profile(
    user_id,
    full_name="Sohibnazar Boysunov",
    age=32,
    sex="male",
    phone_number="+998901234567",
    city_region="Toshkent",
    occupation="Dasturchi",
)
assert updated["full_name"] == "Sohibnazar Boysunov"
assert updated["age"] == 32
assert updated["sex"] == "male"
assert updated["phone_number"] == "+998901234567"
assert updated["city_region"] == "Toshkent"
assert updated["occupation"] == "Dasturchi"

partial = update_patient_profile(user_id, city_region="Samarqand")
assert partial["city_region"] == "Samarqand"
assert partial["full_name"] == "Sohibnazar Boysunov"
assert partial["occupation"] == "Dasturchi"

registered_user_id = register_telegram_user(FakeUpdate())
assert registered_user_id == user_id
registered_profile = get_patient_profile(registered_user_id)
assert registered_profile is not None
assert registered_profile["id"] == profile["id"]

with get_connection() as conn:
    profile_count = conn.execute(
        "SELECT COUNT(*) AS count FROM patient_profiles WHERE user_id = ?",
        (user_id,),
    ).fetchone()["count"]
    message_count = conn.execute("SELECT COUNT(*) AS count FROM messages").fetchone()[
        "count"
    ]

assert profile_count == 1
assert message_count == 0

# Migration: legacy DB without patient_profiles gets the table on init_db().
legacy_db = Path("data/test_step_3_1_legacy.db")
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
    CREATE TABLE conversations (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        status TEXT,
        created_at TEXT
    );
    CREATE TABLE messages (
        id INTEGER PRIMARY KEY,
        conversation_id INTEGER,
        role TEXT,
        content TEXT,
        created_at TEXT
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

assert "patient_profiles" in legacy_tables

print("Step 3.1 OK: patient_profiles table, 1:1 profile, CRUD, registration hook")

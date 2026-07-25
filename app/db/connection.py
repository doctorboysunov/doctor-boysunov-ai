import sqlite3
from pathlib import Path

from app.config import DATABASE_PATH

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")

_PATIENT_PROFILE_COLUMNS = (
    ("height_cm", "INTEGER"),
    ("weight_kg", "INTEGER"),
    ("address", "TEXT"),
    ("allergies", "TEXT"),
    ("chronic_diseases", "TEXT"),
    ("emergency_contact", "TEXT"),
)


def get_connection() -> sqlite3.Connection:
    db_path = Path(DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _run_migrations(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
    }
    if "last_response_id" not in columns:
        conn.execute(
            "ALTER TABLE conversations ADD COLUMN last_response_id TEXT"
        )

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "patient_profiles" not in tables:
        conn.executescript(
            """
            CREATE TABLE patient_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
                full_name TEXT,
                age INTEGER,
                sex TEXT,
                height_cm INTEGER,
                weight_kg INTEGER,
                phone_number TEXT,
                city_region TEXT,
                address TEXT,
                occupation TEXT,
                allergies TEXT,
                chronic_diseases TEXT,
                emergency_contact TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_patient_profiles_user_id
                ON patient_profiles(user_id);
            """
        )
        tables.add("patient_profiles")

    profile_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(patient_profiles)").fetchall()
    }
    for column_name, column_type in _PATIENT_PROFILE_COLUMNS:
        if column_name not in profile_columns:
            conn.execute(
                f"ALTER TABLE patient_profiles ADD COLUMN {column_name} {column_type}"
            )

    if "medical_history" not in tables:
        conn.executescript(
            """
            CREATE TABLE medical_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                record_type TEXT NOT NULL CHECK (
                    record_type IN (
                        'symptom',
                        'diagnosis',
                        'mri',
                        'ct',
                        'emg',
                        'laboratory',
                        'treatment',
                        'consultation'
                    )
                ),
                content TEXT NOT NULL,
                notes TEXT,
                event_date TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_medical_history_user_id
                ON medical_history(user_id, id);

            CREATE INDEX IF NOT EXISTS idx_medical_history_user_type
                ON medical_history(user_id, record_type, id);
            """
        )
        tables.add("medical_history")

    if "patient_files" not in tables:
        conn.executescript(
            """
            CREATE TABLE patient_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                medical_history_id INTEGER NOT NULL REFERENCES medical_history(id),
                file_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                mime_type TEXT,
                file_category TEXT NOT NULL CHECK (
                    file_category IN ('image', 'pdf', 'word', 'document')
                ),
                telegram_file_id TEXT,
                caption TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_patient_files_user_id
                ON patient_files(user_id, id);
            """
        )


def init_db() -> None:
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(schema)
        _run_migrations(conn)
        conn.commit()

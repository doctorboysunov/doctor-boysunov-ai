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
    ("country", "TEXT"),
    ("region", "TEXT"),
    ("district", "TEXT"),
    ("latitude", "REAL"),
    ("longitude", "REAL"),
    ("phone_normalized", "TEXT"),
    ("email", "TEXT"),
    ("mobile_push_token", "TEXT"),
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

    if "users" in tables:
        user_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "registration_source" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN registration_source TEXT NOT NULL DEFAULT 'telegram'"
            )

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
                country TEXT,
                region TEXT,
                district TEXT,
                city_region TEXT,
                address TEXT,
                latitude REAL,
                longitude REAL,
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

    if "appointments" not in tables:
        conn.executescript(
            """
            CREATE TABLE appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES users(id),
                doctor_name TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                complaint TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK (
                    status IN ('pending', 'confirmed', 'cancelled')
                ),
                confirmation_time TEXT,
                confirmed_by TEXT,
                admin_notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_appointments_patient_id
                ON appointments(patient_id, id);

            CREATE INDEX IF NOT EXISTS idx_appointments_status
                ON appointments(status, id);

            CREATE INDEX IF NOT EXISTS idx_appointments_date
                ON appointments(appointment_date, id);
            """
        )
        tables.add("appointments")

    if "appointments" in tables:
        appointment_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(appointments)").fetchall()
        }
        for column_name, column_type in (
            ("confirmation_time", "TEXT"),
            ("confirmed_by", "TEXT"),
            ("admin_notes", "TEXT"),
            ("updated_at", "TEXT"),
        ):
            if column_name not in appointment_columns:
                conn.execute(
                    f"ALTER TABLE appointments ADD COLUMN {column_name} {column_type}"
                )
        if "updated_at" in appointment_columns or "updated_at" in {
            row[1]
            for row in conn.execute("PRAGMA table_info(appointments)").fetchall()
        }:
            conn.execute(
                """
                UPDATE appointments
                SET updated_at = created_at
                WHERE updated_at IS NULL OR updated_at = ''
                """
            )

    if "patient_treatments" not in tables:
        conn.executescript(
            """
            CREATE TABLE patient_treatments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES users(id),
                started_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active' CHECK (
                    status IN ('active', 'completed', 'cancelled')
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_patient_treatments_patient_id
                ON patient_treatments(patient_id, id);
            """
        )
        tables.add("patient_treatments")

    if "follow_ups" not in tables:
        conn.executescript(
            """
            CREATE TABLE follow_ups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES users(id),
                treatment_id INTEGER NOT NULL REFERENCES patient_treatments(id),
                sequence_number INTEGER NOT NULL,
                follow_up_kind TEXT NOT NULL CHECK (
                    follow_up_kind IN ('check_in', 'examination', 'preventive')
                ),
                scheduled_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'scheduled' CHECK (
                    status IN ('scheduled', 'notified', 'completed', 'cancelled')
                ),
                invitation_text TEXT NOT NULL,
                notified_at TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_follow_ups_patient_id
                ON follow_ups(patient_id, sequence_number);

            CREATE INDEX IF NOT EXISTS idx_follow_ups_scheduled
                ON follow_ups(status, scheduled_date);
            """
        )

    if "patient_communication_channels" not in tables:
        conn.executescript(
            """
            CREATE TABLE patient_communication_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES users(id),
                channel TEXT NOT NULL CHECK (
                    channel IN ('telegram', 'mobile_push', 'sms', 'email')
                ),
                address TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                verified_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(patient_id, channel)
            );

            CREATE INDEX IF NOT EXISTS idx_patient_channels_patient_id
                ON patient_communication_channels(patient_id, channel);
            """
        )
        tables.add("patient_communication_channels")

    if "communication_deliveries" not in tables:
        conn.executescript(
            """
            CREATE TABLE communication_deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES users(id),
                channel TEXT NOT NULL CHECK (
                    channel IN ('telegram', 'mobile_push', 'sms', 'email')
                ),
                source_type TEXT NOT NULL,
                source_id TEXT,
                message_text TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('sent', 'delivered', 'failed', 'replied')
                ),
                provider_name TEXT,
                provider_message_id TEXT,
                error_message TEXT,
                attempt_number INTEGER NOT NULL DEFAULT 1,
                parent_delivery_id INTEGER REFERENCES communication_deliveries(id),
                replied_at TEXT,
                reply_text TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_communication_deliveries_patient
                ON communication_deliveries(patient_id, id);

            CREATE INDEX IF NOT EXISTS idx_communication_deliveries_source
                ON communication_deliveries(source_type, source_id, id);
            """
        )

    if "dashboard_snapshots" not in tables:
        conn.executescript(
            """
            CREATE TABLE dashboard_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                period TEXT NOT NULL DEFAULT 'today',
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_dashboard_snapshots_date_period
                ON dashboard_snapshots(snapshot_date, period);
            """
        )

    if "admin_telegram_ids" not in tables:
        conn.executescript(
            """
            CREATE TABLE admin_telegram_ids (
                telegram_id INTEGER PRIMARY KEY,
                source TEXT NOT NULL DEFAULT 'env',
                created_at TEXT NOT NULL
            );
            """
        )


def init_db() -> None:
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(schema)
        _run_migrations(conn)
        conn.commit()

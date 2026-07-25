CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    username TEXT,
    full_name TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'active',
    last_response_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
    ON messages(conversation_id, id);

CREATE TABLE IF NOT EXISTS patient_profiles (
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

CREATE TABLE IF NOT EXISTS medical_history (
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

CREATE TABLE IF NOT EXISTS patient_files (
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

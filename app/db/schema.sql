CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE,
    username TEXT,
    full_name TEXT,
    registration_source TEXT NOT NULL DEFAULT 'telegram',
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
    email TEXT,
    mobile_push_token TEXT,
    phone_normalized TEXT UNIQUE,
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

CREATE TABLE IF NOT EXISTS appointments (
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

CREATE TABLE IF NOT EXISTS patient_treatments (
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

CREATE TABLE IF NOT EXISTS follow_ups (
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

CREATE TABLE IF NOT EXISTS patient_communication_channels (
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

CREATE TABLE IF NOT EXISTS communication_deliveries (
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

CREATE TABLE IF NOT EXISTS dashboard_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    period TEXT NOT NULL DEFAULT 'today',
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dashboard_snapshots_date_period
    ON dashboard_snapshots(snapshot_date, period);

CREATE TABLE IF NOT EXISTS admin_telegram_ids (
    telegram_id INTEGER PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'env',
    created_at TEXT NOT NULL
);

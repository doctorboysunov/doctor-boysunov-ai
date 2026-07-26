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
    clinic_location_id INTEGER REFERENCES clinic_locations(id),
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
        status IN ('scheduled', 'notified', 'completed', 'cancelled', 'no_response')
    ),
    invitation_text TEXT NOT NULL,
    notified_at TEXT,
    completed_at TEXT,
    response_outcome TEXT NOT NULL DEFAULT 'pending' CHECK (
        response_outcome IN ('pending', 'good', 'no_change', 'worse', 'no_response')
    ),
    patient_reply_text TEXT,
    high_priority INTEGER NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS emr_visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES users(id),
    visit_date TEXT NOT NULL,
    main_complaint TEXT,
    examination_findings TEXT,
    neurological_examination TEXT,
    preliminary_diagnosis TEXT,
    final_diagnosis TEXT,
    icd10_code TEXT,
    recommended_examinations TEXT,
    treatment_plan TEXT,
    procedures_performed TEXT,
    follow_up_schedule TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_emr_visits_patient_id
    ON emr_visits(patient_id, visit_date DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_emr_visits_visit_date
    ON emr_visits(visit_date, id);

CREATE TABLE IF NOT EXISTS consultation_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES users(id),
    visit_id INTEGER NOT NULL REFERENCES emr_visits(id),
    complaint_category TEXT NOT NULL,
    phase TEXT NOT NULL CHECK (phase IN ('collecting', 'complete', 'emergency')),
    asked_question_ids TEXT NOT NULL DEFAULT '[]',
    answers_json TEXT NOT NULL DEFAULT '{}',
    current_question_id TEXT,
    summary_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_consultation_sessions_patient
    ON consultation_sessions(patient_id, phase, id DESC);

CREATE TABLE IF NOT EXISTS care_manager_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES users(id),
    follow_up_id INTEGER REFERENCES follow_ups(id),
    sequence_number INTEGER,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'check_in_sent',
            'examination_invite',
            'preventive_invite',
            'reply_received',
            'retry_sent',
            'no_response_marked',
            'doctor_notified'
        )
    ),
    outcome TEXT CHECK (
        outcome IN ('pending', 'good', 'no_change', 'worse', 'no_response')
    ),
    message_text TEXT,
    reply_text TEXT,
    event_date TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_care_manager_patient_id
    ON care_manager_records(patient_id, event_date DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_care_manager_follow_up_id
    ON care_manager_records(follow_up_id, id);

CREATE TABLE IF NOT EXISTS clinic_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_name TEXT NOT NULL,
    staff_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('doctor', 'student', 'assistant')),
    specialty TEXT,
    address TEXT NOT NULL,
    google_maps_link TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    working_days TEXT NOT NULL DEFAULT 'mon,tue,wed,thu,fri',
    working_hours_start TEXT NOT NULL DEFAULT '09:00',
    working_hours_end TEXT NOT NULL DEFAULT '18:00',
    phone TEXT,
    services TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    sort_priority INTEGER NOT NULL DEFAULT 100,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clinic_locations_active
    ON clinic_locations(is_active, role, sort_priority);

CREATE INDEX IF NOT EXISTS idx_clinic_locations_specialty
    ON clinic_locations(specialty, is_active);

CREATE TABLE IF NOT EXISTS admin_sessions (
    admin_telegram_id INTEGER PRIMARY KEY,
    mode TEXT NOT NULL DEFAULT 'normal_ai' CHECK (mode IN ('normal_ai', 'doctor_visit', 'patient_registration')),
    active_patient_id INTEGER REFERENCES users(id),
    active_patient_name TEXT,
    visit_id INTEGER REFERENCES emr_visits(id),
    registration_started_at TEXT,
    updated_at TEXT NOT NULL
);

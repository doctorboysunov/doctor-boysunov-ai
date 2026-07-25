from app.settings import get_settings

_settings = get_settings()

BOT_TOKEN = _settings.telegram_bot_token
OPENAI_API_KEY = _settings.openai_api_key
OPENAI_MODEL = _settings.openai_model
DATABASE_PATH = _settings.database_path
PATIENT_FILES_PATH = _settings.patient_files_path
ADMIN_TELEGRAM_IDS = _settings.admin_ids
PATIENT_INTAKE_API_KEY = _settings.patient_intake_api_key
DASHBOARD_API_KEY = _settings.dashboard_api_key
DASHBOARD_MORNING_HOUR = _settings.dashboard_morning_hour
ADMIN_SETUP_PIN = _settings.admin_setup_pin
SMS_ENABLED = _settings.sms_enabled
PUSH_ENABLED = _settings.push_enabled
EMAIL_ENABLED = _settings.email_enabled

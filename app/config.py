from app.settings import get_settings

_settings = get_settings()

BOT_TOKEN = _settings.telegram_bot_token
OPENAI_API_KEY = _settings.openai_api_key
OPENAI_MODEL = _settings.openai_model
DATABASE_PATH = _settings.database_path
PATIENT_FILES_PATH = _settings.patient_files_path

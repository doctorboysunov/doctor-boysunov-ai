import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
assert "data/" in gitignore.splitlines(), gitignore

env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
assert "DATABASE_PATH=data/clinic.db" in env_example
assert "OPENAI_MODEL=gpt-5.5" in env_example

os.environ["DATABASE_PATH"] = "data/custom_test.db"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.settings import Settings, get_settings

get_settings.cache_clear()
settings = Settings()
assert Path(settings.database_path).name == "custom_test.db"
assert settings.openai_model == "gpt-5.5"

get_settings.cache_clear()
loaded = get_settings()
assert Path(loaded.database_path).name == "custom_test.db"

print("Step 2.5 OK: data/ gitignored, env example updated, settings aliases verified")

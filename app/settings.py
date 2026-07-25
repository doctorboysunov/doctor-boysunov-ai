from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(..., validation_alias="TELEGRAM_BOT_TOKEN")
    openai_api_key: str = Field(..., validation_alias="OPENAI_API_KEY")

    database_path: str = Field(
        default="data/clinic.db",
        validation_alias="DATABASE_PATH",
    )
    openai_model: str = Field(
        default="gpt-5.5",
        validation_alias="OPENAI_MODEL",
    )

    @field_validator("database_path", mode="before")
    @classmethod
    def resolve_database_path(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            return str(path)
        return str(PROJECT_ROOT / path)

@lru_cache
def get_settings() -> Settings:
    return Settings()

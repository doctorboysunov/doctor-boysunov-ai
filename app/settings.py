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
    patient_files_path: str = Field(
        default="data/patient_files",
        validation_alias="PATIENT_FILES_PATH",
    )
    openai_model: str = Field(
        default="gpt-5.5",
        validation_alias="OPENAI_MODEL",
    )
    admin_telegram_ids: str = Field(
        default="",
        validation_alias="ADMIN_TELEGRAM_IDS",
    )
    patient_intake_api_key: str = Field(
        default="",
        validation_alias="PATIENT_INTAKE_API_KEY",
    )
    dashboard_api_key: str = Field(
        default="",
        validation_alias="DASHBOARD_API_KEY",
    )
    dashboard_morning_hour: int = Field(
        default=7,
        validation_alias="DASHBOARD_MORNING_HOUR",
    )
    sms_enabled: bool = Field(
        default=True,
        validation_alias="SMS_ENABLED",
    )
    push_enabled: bool = Field(
        default=True,
        validation_alias="PUSH_ENABLED",
    )
    email_enabled: bool = Field(
        default=True,
        validation_alias="EMAIL_ENABLED",
    )
    admin_setup_pin: str = Field(
        default="",
        validation_alias="ADMIN_SETUP_PIN",
    )

    @property
    def admin_ids(self) -> tuple[int, ...]:
        if not self.admin_telegram_ids.strip():
            return ()
        ids: list[int] = []
        for part in self.admin_telegram_ids.split(","):
            cleaned = part.strip()
            if cleaned:
                ids.append(int(cleaned))
        return tuple(ids)

    @field_validator("database_path", mode="before")
    @classmethod
    def resolve_database_path(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            return str(path)
        return str(PROJECT_ROOT / path)

    @field_validator("patient_files_path", mode="before")
    @classmethod
    def resolve_patient_files_path(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            return str(path)
        return str(PROJECT_ROOT / path)

@lru_cache
def get_settings() -> Settings:
    return Settings()

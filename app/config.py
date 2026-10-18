from datetime import timedelta

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    database_url: str = ""
    # Required: no default, so a missing, empty or short key stops the app at import.
    secret_key: str = Field(min_length=32)


settings = Settings()

# Access
SESSION_TTL = timedelta(days=7)
CONSENT_VERSION = "2026-10-18"
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128
INVITE_MAX_COUNT = 1000
INVITE_MAX_TTL_DAYS = 90

# Profile. Keys are stored in the DB; labels are UI text. Change without migrations.
GENDERS: dict[str, str] = {"man": "Мужчина", "woman": "Женщина", "other": "Другое"}
MODES: dict[str, str] = {"normal": "Обычный", "experimental": "Экспериментальный"}

# Result input
PASTE_MAX_CHARS = 20_000

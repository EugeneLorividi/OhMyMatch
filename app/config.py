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

# Screenshot OCR (section 5.2)
OCR_MAX_FILES = 3
OCR_MAX_FILE_BYTES = 8 * 1024 * 1024
OCR_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
OCR_MAX_INPUT_PIXELS = 40_000_000
OCR_MAX_WORK_PIXELS = 30_000_000  # after upscaling
OCR_FUZZY_THRESHOLD = 85  # rapidfuzz score; below this a name is uncertain
OCR_FUZZY_FLOOR = 70  # below this the line is not treated as a category at all
OCR_FUZZY_MARGIN = 5  # runner-up this close to the best match makes it uncertain
OCR_MIN_CONFIDENCE = 60  # Tesseract word confidence
OCR_CONCURRENCY = 2
OCR_QUEUE_WAIT_SECONDS = 30
OCR_TESSERACT_TIMEOUT_SECONDS = 20

# Request body limits; nginx enforces the same outside.
MAX_BODY_BYTES = 1024 * 1024
MAX_UPLOAD_BODY_BYTES = 25 * 1024 * 1024

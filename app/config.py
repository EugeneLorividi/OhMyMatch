from dataclasses import dataclass
from datetime import timedelta

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    database_url: str = ""
    # Required: no default, so a missing, empty or short key stops the app at import.
    secret_key: str = Field(min_length=32)
    # Peers whose X-Forwarded-For is trusted (comma-separated IPs or CIDRs); empty trusts none.
    trusted_proxies: str = ""


settings = Settings()

# Access
SESSION_TTL = timedelta(days=7)
CONSENT_VERSION = "2026-10-18.3"  # bumped: uk/en text, inference warning, privacy link
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128
INVITE_MAX_COUNT = 1000
INVITE_MAX_TTL_DAYS = 90

# Profile. Keys are stored in the DB; labels are locale keys gender.<key> and mode.<key>.
# Change without migrations.
GENDERS: tuple[str, ...] = ("man", "woman", "other")
MODES: tuple[str, ...] = ("normal", "experimental")

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

# Matching (section 7). Hypotheses, tuned after launch.
ACTIVE_THRESHOLD = 65
CURIOUS_LOW = 30
CURIOUS_FACTOR = 0.5
NONMONO_LOW = 35
# (WEIGHT_ROLES, WEIGHT_STYLE) by the viewer's mode
WEIGHTS: dict[str, tuple[float, float]] = {"normal": (0.75, 0.25), "experimental": (0.6, 0.4)}
PAIR_WEIGHTS: dict[tuple[str, str], float] = {}  # default weight 1 for every pair
FEED_PAGE_SIZE = 20
EXPLAIN_MAX_AXES = 5


# Rate limits (section 9). In memory only; windows are rolling.
@dataclass(frozen=True)
class Rule:
    name: str
    limit: int
    window_seconds: int


HOUR = 3600
DAY = 24 * HOUR
LOGIN_PER_IP = Rule("login_ip", 30, 15 * 60)
LOGIN_FAILS_PER_HANDLE = Rule("login_handle", 10, 15 * 60)
REGISTER_PER_IP = Rule("register_ip", 20, HOUR)
RECOVER_PER_IP = Rule("recover_ip", 10, HOUR)
RECOVER_FAILS_PER_HANDLE = Rule("recover_handle", 5, HOUR)
ACCOUNT_ACTIONS_PER_USER = Rule("account_user", 10, HOUR)  # password change, deletion
OCR_PER_USER = Rule("ocr_user", 20, DAY)
FEED_PAGES_PER_USER = Rule("feed_user", 20, DAY)
REACTIONS_PER_USER = Rule("react_user", 100, DAY)
RESULT_SAVES_PER_USER = Rule("result_user", 5, DAY)
DISLIKES_SAVES_PER_USER = Rule("dislikes_user", 5, DAY)
PROFILE_SAVES_PER_USER = Rule("profile_user", 5, DAY)

# Retention promised on /privacy; enforced by deploy/backup (backups) and nginx logrotate (logs).
BACKUP_RETENTION_DAYS = 14
PROXY_LOG_RETENTION_DAYS = 7

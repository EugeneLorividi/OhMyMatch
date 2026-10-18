from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    database_url: str = ""
    # Required: no default, so a missing, empty or short key stops the app at import.
    secret_key: str = Field(min_length=32)


settings = Settings()

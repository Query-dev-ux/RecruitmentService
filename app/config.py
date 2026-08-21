from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    INTERNAL_SERVICE_TOKEN: str
    DATABASE_URL: str

    HH_CLIENT_ID: Optional[str] = None
    HH_CLIENT_SECRET: Optional[str] = None
    HH_REDIRECT_URI: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

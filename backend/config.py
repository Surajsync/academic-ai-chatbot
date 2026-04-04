from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "secret"

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),  # local use
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

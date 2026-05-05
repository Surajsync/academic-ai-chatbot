import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "secret"

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    GMAIL_ADDRESS: str | None = None
    GMAIL_APP_PASSWORD: str | None = None
    RESEND_API_KEY: str | None = None
    RESEND_FROM_EMAIL: str | None = None
    REQUIRE_REGISTRATION_OTP: bool = False
    RESET_TOKEN_EXPIRE_MINS: int = 15
    APP_BASE_URL: str = Field(
        default_factory=lambda: os.getenv(
            "APP_BASE_URL",
            os.getenv("RENDER_EXTERNAL_URL", "http://127.0.0.1:8000"),
        )
    )

    OPENAI_API_KEY: str | None = None
    LLM_MODEL: str = "gpt-4o-mini"
    ENABLE_LLM: bool = False

    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def _sanitize_database_url(raw: str) -> str:
    if not raw:
        return raw
    s = raw.strip()
    # Handle values pasted from Neon/psql CLI like: psql 'postgresql://...'
    if s.startswith("psql "):
        # remove leading `psql ` and any surrounding quotes
        s = s[4:].strip()
    # strip surrounding single/double quotes if present
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        s = s[1:-1]
    return s


# Defensive sanitization for common mis-pastes in Render env values
try:
    settings.DATABASE_URL = _sanitize_database_url(settings.DATABASE_URL)
except Exception:
    # Keep original value if anything unexpected happens; let startup show a clear error
    pass

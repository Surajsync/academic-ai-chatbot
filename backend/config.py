from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "secret"

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    GMAIL_ADDRESS: str | None = None
    GMAIL_APP_PASSWORD: str | None = None
    RESET_TOKEN_EXPIRE_MINS: int = 15
    APP_BASE_URL: str = "http://127.0.0.1:8000"

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

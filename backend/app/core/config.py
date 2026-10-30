from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TestForge Backend"
    app_version: str = "0.1.0"
    environment: str = "development"

    api_prefix: str = "/api/v1"

    host: str = "127.0.0.1"
    port: int = 8000

    frontend_url: str = "http://localhost:5173"

    database_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_api_key: str | None = None
    google_api_key: str | None = None
    groq_api_key: str | None = None
    deepseek_api_key: str | None = None

    openai_model: str | None = None
    gemini_model: str | None = None
    llama_model: str | None = None
    deepseek_model: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
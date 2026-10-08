from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "FitBuddy"
    database_url: str = "sqlite:///./fitbuddy.db"
    gemini_api_key: str = ""
    gemini_workout_model: str = "gemini-3-flash-preview"
    gemini_tip_model: str = "gemini-3-flash-preview"
    admin_token: str = "change-this-before-exposing-the-dashboard"
    allow_demo_ai: bool = True

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

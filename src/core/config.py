import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/imobi_sdr"

    # OpenAI / LLM Configuration
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"

    # Gemini Configuration
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"


    # Chatwoot Configuration
    CHATWOOT_URL: Optional[str] = None
    CHATWOOT_ACCESS_TOKEN: Optional[str] = None
    CHATWOOT_ACCOUNT_ID: Optional[int] = None

    @field_validator("CHATWOOT_ACCOUNT_ID", mode="before")
    @classmethod
    def parse_empty_int(cls, v):
        if v == "" or v is None:
            return None
        return int(v)


    # Evolution API Configuration
    EVOLUTION_API_URL: Optional[str] = None
    EVOLUTION_API_KEY: Optional[str] = None
    EVOLUTION_WEBHOOK_URL: Optional[str] = None

    # General App Configuration
    APP_NAME: str = "Imobi SDR Backend"
    APP_ENV: str = "development"

settings = Settings()

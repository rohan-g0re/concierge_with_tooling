"""
Configuration — reads environment variables for the Compass backend.
All secrets are injected via .env (loaded by the launcher) or real env.
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str = ""
    openai_api_key: str = ""
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    debug: bool = False
    llm_mode: str = "auto"  # 'auto' | 'stub' | 'gemini'

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()

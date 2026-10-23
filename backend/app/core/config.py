from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "쉿간표 PoC"
    model_version: str = "poc-0.1.0"
    timezone: str = "Asia/Seoul"
    slot_minutes: int = 15
    extractor_mode: str = "mock"
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    data_dir: Path = Path(__file__).parents[1] / "data"
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SHH_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

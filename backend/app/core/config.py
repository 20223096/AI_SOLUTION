from functools import lru_cache
from pathlib import Path
from pydantic import AliasChoices, Field, SecretStr

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
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])
    data_dir: Path = Path(__file__).parents[1] / "data"
    juso_search_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("JUSO_SEARCH_API_KEY", "SHH_JUSO_SEARCH_API_KEY"),
    )
    juso_coord_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("JUSO_COORD_API_KEY", "SHH_JUSO_COORD_API_KEY"),
    )
    juso_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    resident_notice_store_path: Path = Path(__file__).parents[3] / "runtime" / "resident_notices.json"
    recommendation_snapshot_store_path: Path = Path(__file__).parents[3] / "runtime" / "recommendation_snapshots.json"
    staff_api_allowed_hosts: list[str] = Field(default_factory=lambda: ["127.0.0.1", "::1", "localhost", "testclient"])
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parents[3] / ".env",
        env_prefix="SHH_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

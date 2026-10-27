from functools import lru_cache
from pathlib import Path
from pydantic import AliasChoices, Field, SecretStr

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parents[3]
BACKEND_ROOT = Path(__file__).parents[2]


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
    resident_notice_store_path: Path = PROJECT_ROOT / "runtime" / "resident_notices.json"
    recommendation_snapshot_store_path: Path = PROJECT_ROOT / "runtime" / "recommendation_snapshots.json"
    staff_api_allowed_hosts: list[str] = Field(default_factory=lambda: ["127.0.0.1", "::1", "localhost", "testclient"])
    model_config = SettingsConfigDict(
        # Root .env remains a migration fallback; backend/.env wins when both exist.
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_prefix="SHH_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

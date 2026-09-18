"""Configuration management for hermes-share."""

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database paths
    hermes_db_path: Path = Field(
        default_factory=lambda: Path(
            os.path.expanduser(os.getenv("HERMES_DB_PATH", "~/.hermes/state.db"))
        ).resolve()
    )
    share_db_path: Path = Field(
        default_factory=lambda: Path(
            os.path.expanduser(os.getenv("SHARE_DB_PATH", "./share.db"))
        ).resolve()
    )

    # Authentication & Security
    management_api_key: str = Field(
        default_factory=lambda: os.getenv("MANAGEMENT_API_KEY", "default-dev-key")
    )
    base_url: str = Field(
        default_factory=lambda: os.getenv("BASE_URL", "http://localhost:8000")
    )
    default_ttl_seconds: int = Field(
        default_factory=lambda: int(os.getenv("DEFAULT_TTL_SECONDS", "0"))
    )
    redact_secrets: bool = Field(
        default_factory=lambda: os.getenv("REDACT_SECRETS", "true").lower()
        in ("1", "true", "yes")
    )

    # Server & UI
    host: str = "0.0.0.0"
    port: int = 8000
    static_dir: Path | None = Field(
        default_factory=lambda: Path("./web/dist").resolve()
        if Path("./web/dist").exists()
        else None
    )


settings = Settings()

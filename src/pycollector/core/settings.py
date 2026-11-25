"""Base settings using pydantic-settings with .env file support.

Extend ``BaseCollectorSettings`` in your application to add
entity-specific configuration fields.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseCollectorSettings(BaseSettings):
    """Foundation settings for any web data collection system.

    Override defaults via environment variables or a ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Application --------------------------------------------------------
    app_name: str = Field(default="pycollector", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    # --- Database -----------------------------------------------------------
    database_url: str = Field(
        default="sqlite+pysqlite:///./local_dev.db",
        alias="DATABASE_URL",
    )

    # --- Scheduler ----------------------------------------------------------
    scheduler_enabled: bool = Field(default=False, alias="SCHEDULER_ENABLED")
    scheduler_poll_interval_seconds: int = Field(
        default=60,
        alias="SCHEDULER_POLL_INTERVAL_SECONDS",
        ge=1,
    )
    scheduler_weekly_day: str = Field(default="MONDAY", alias="SCHEDULER_WEEKLY_DAY")
    scheduler_weekly_hour: int = Field(default=9, alias="SCHEDULER_WEEKLY_HOUR", ge=0, le=23)
    scheduler_weekly_minute: int = Field(default=0, alias="SCHEDULER_WEEKLY_MINUTE", ge=0, le=59)
    scheduler_max_retry_count: int = Field(
        default=1,
        alias="SCHEDULER_MAX_RETRY_COUNT",
        ge=0,
    )
    scheduler_retry_interval_seconds: int = Field(
        default=60,
        alias="SCHEDULER_RETRY_INTERVAL_SECONDS",
        ge=0,
    )

    # --- HTTP ---------------------------------------------------------------
    collector_http_timeout_seconds: int = Field(
        default=30,
        alias="COLLECTOR_HTTP_TIMEOUT_SECONDS",
    )


@lru_cache
def get_settings() -> BaseCollectorSettings:
    """Return a cached singleton of the settings."""
    return BaseCollectorSettings()
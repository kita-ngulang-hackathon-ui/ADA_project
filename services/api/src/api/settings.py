"""Service settings loaded from environment / .env.

Every value here either has a safe, explicit default (ports, timeouts) or is
required with no default -- required fields raise at import/construction
time rather than silently falling back to a guessed value (CLAUDE.md's
"never invent a number" rule). `__TBD__` placeholders from .env.example are
treated as *missing*: get_settings() refuses to start with one still set.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_TBD_SENTINELS = {"", "__TBD__"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    database_url: str
    # Ingestion-side writes (raw_events, outcome_events, delivery acks) need the
    # app_worker grants from migration 0006; the console role has none of them.
    # Empty falls back to database_url, which only works if that URL is already
    # a role with those grants.
    worker_database_url: str = ""
    db_pool_size: int = 10
    db_pool_max_overflow: int = 5
    db_echo: bool = False

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000"
    api_request_timeout_seconds: int = 15
    ingest_max_batch_size: int = 500
    ingest_rate_limit_per_min: int = 1000
    console_rate_limit_per_min: int = 300

    api_key_hash_pepper: str
    console_session_secret: str
    console_demo_reviewers: str
    console_require_reviewer_id: bool = True
    console_session_ttl_seconds: int = 43_200  # 12h; the cookie carries its own expiry
    measurement_min_arm_size: int = 30

    @field_validator(
        "database_url", "api_key_hash_pepper", "console_session_secret", "console_demo_reviewers"
    )
    @classmethod
    def _reject_tbd(cls, v: str, info) -> str:
        if v in _TBD_SENTINELS:
            raise ValueError(
                f"{info.field_name} is required and must not be left as __TBD__ or empty "
                "-- fill in .env; this application fails loudly rather than defaulting"
            )
        return v

    @property
    def ingest_database_url(self) -> str:
        return self.worker_database_url or self.database_url

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def demo_reviewer_set(self) -> frozenset[str]:
        return frozenset(r.strip() for r in self.console_demo_reviewers.split(",") if r.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()

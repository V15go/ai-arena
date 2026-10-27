"""Environment-driven settings. Importing this module never needs credentials."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]
MIN_PROD_TOKEN_LENGTH = 24


def normalize_database_url(url: str) -> str:
    """Turn a Neon-style URL into one SQLAlchemy + asyncpg accepts.

    Neon hands out ``postgresql://...?sslmode=require&channel_binding=require``.
    asyncpg wants ``ssl=`` and does not know ``channel_binding``.
    """
    parts = urlsplit(url)
    if not parts.scheme.startswith("postgres"):
        return url
    query: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key == "channel_binding":
            continue
        query.append(("ssl" if key == "sslmode" else key, value))
    return urlunsplit(
        ("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    web_origin: str = "http://localhost:5173"

    # Neon: pooled URL for the app, direct URL for migrations.
    database_url: str | None = None
    database_url_direct: str | None = None

    api_auth_token: SecretStr | None = None

    meta_model_api_key: SecretStr | None = None
    meta_model_base_url: str | None = None
    meta_planner_model: str | None = None
    meta_fast_model: str | None = None

    sandbox_provider: Literal["fake", "modal"] = "fake"
    modal_token_id: SecretStr | None = None
    modal_token_secret: SecretStr | None = None
    modal_sandbox_image: str | None = None
    sandbox_timeout_seconds: int = 60

    max_concurrency: int = 3
    max_workflow_tasks: int = 20
    max_task_attempts: int = 2
    max_model_calls_per_run: int = 50

    @field_validator("database_url", "database_url_direct")
    @classmethod
    def _normalize_db_url(cls, value: str | None) -> str | None:
        return normalize_database_url(value) if value else None

    @field_validator("max_concurrency")
    @classmethod
    def _bounded_concurrency(cls, value: int) -> int:
        if not 1 <= value <= 16:
            raise ValueError("MAX_CONCURRENCY must be between 1 and 16")
        return value

    @model_validator(mode="after")
    def _check_cross_field_rules(self) -> Self:
        if self.app_env == "production":
            token = self.api_auth_token.get_secret_value() if self.api_auth_token else ""
            if len(token) < MIN_PROD_TOKEN_LENGTH:
                raise ValueError(
                    f"API_AUTH_TOKEN must be at least {MIN_PROD_TOKEN_LENGTH} chars in production"
                )
        if self.sandbox_provider == "modal":
            missing = [
                name
                for name, value in (
                    ("MODAL_TOKEN_ID", self.modal_token_id),
                    ("MODAL_TOKEN_SECRET", self.modal_token_secret),
                    ("MODAL_SANDBOX_IMAGE", self.modal_sandbox_image),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"SANDBOX_PROVIDER=modal requires {', '.join(missing)}")
        return self

    @property
    def migration_database_url(self) -> str | None:
        return self.database_url_direct or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()

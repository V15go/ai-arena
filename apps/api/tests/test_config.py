import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings, normalize_database_url
from tests.conftest import make_settings


def test_neon_url_is_normalized_for_asyncpg() -> None:
    url = "postgresql://u:p@ep-x-pooler.neon.tech/db?sslmode=require&channel_binding=require"
    assert (
        normalize_database_url(url)
        == "postgresql+asyncpg://u:p@ep-x-pooler.neon.tech/db?ssl=require"
    )
    assert normalize_database_url("postgres://u:p@h/db").startswith("postgresql+asyncpg://")


def test_non_postgres_url_is_untouched() -> None:
    assert normalize_database_url("sqlite+aiosqlite:///x.db") == "sqlite+aiosqlite:///x.db"


def test_migrations_prefer_direct_url() -> None:
    s = make_settings(database_url="postgresql://a/db", database_url_direct="postgresql://b/db")
    assert s.migration_database_url == "postgresql+asyncpg://b/db"


def test_defaults_need_no_credentials() -> None:
    s = Settings(_env_file=None)
    assert s.sandbox_provider == "fake"
    assert s.database_url is None


def test_modal_requires_credentials() -> None:
    with pytest.raises(ValidationError, match="MODAL_TOKEN_ID"):
        make_settings(sandbox_provider="modal")


def test_production_requires_strong_token() -> None:
    with pytest.raises(ValidationError, match="API_AUTH_TOKEN"):
        make_settings(app_env="production", api_auth_token=None)
    with pytest.raises(ValidationError, match="API_AUTH_TOKEN"):
        make_settings(app_env="production", api_auth_token=SecretStr("too-short"))
    assert (
        make_settings(app_env="production", api_auth_token=SecretStr("x" * 24)).app_env
        == "production"
    )


def test_concurrency_is_bounded() -> None:
    with pytest.raises(ValidationError):
        make_settings(max_concurrency=99)


def test_secrets_do_not_leak_in_repr() -> None:
    assert "test-token" not in repr(make_settings())

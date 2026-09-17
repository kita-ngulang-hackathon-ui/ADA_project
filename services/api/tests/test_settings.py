"""Settings never silently defaults a required, security-relevant value."""
import pytest
from api.settings import Settings
from pydantic import ValidationError


def _base_kwargs(**overrides):
    kwargs = dict(
        database_url="postgresql+psycopg://app_console:x@localhost:5432/retention",
        api_key_hash_pepper="pepper",
        console_session_secret="secret",
        console_demo_reviewers="ops_reviewer_1,ops_reviewer_2",
    )
    kwargs.update(overrides)
    return kwargs


def test_valid_settings_construct(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(_env_file=None, **_base_kwargs())
    assert settings.demo_reviewer_set == {"ops_reviewer_1", "ops_reviewer_2"}


@pytest.mark.parametrize("field", ["database_url", "api_key_hash_pepper", "console_session_secret", "console_demo_reviewers"])
def test_tbd_placeholder_rejected(field, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    kwargs = _base_kwargs(**{field: "__TBD__"})
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)


@pytest.mark.parametrize("field", ["database_url", "api_key_hash_pepper", "console_session_secret", "console_demo_reviewers"])
def test_empty_string_rejected(field, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    kwargs = _base_kwargs(**{field: ""})
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)


def test_cors_origins_parsed_as_list(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(_env_file=None, api_cors_origins="http://a.com, http://b.com", **_base_kwargs())
    assert settings.cors_origins_list == ["http://a.com", "http://b.com"]

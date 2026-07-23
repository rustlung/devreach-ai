import pytest

from app.core.config import Settings
from tests.conftest import readable_test_id


@readable_test_id("настройки загружаются из окружения")
def test_settings_are_loaded_from_environment(monkeypatch, tmp_path, _case_id) -> None:
    """CONFIG-001: настройки корректно загружаются из переменных окружения."""
    monkeypatch.setenv("APP_NAME", "devreach-test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'env.sqlite3'}")
    monkeypatch.setenv("CORS_ORIGINS", "http://one.test, http://two.test")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "env.log"))
    monkeypatch.setenv("LOG_MAX_BYTES", "2048")
    monkeypatch.setenv("LOG_BACKUP_COUNT", "2")
    monkeypatch.setenv("OPENAI_BASE_URL", " https://api.proxyapi.ru/openai/v1 ")
    monkeypatch.setenv("CONTACT_RATE_LIMIT_REQUESTS", "5")
    monkeypatch.setenv("CONTACT_RATE_LIMIT_WINDOW_SECONDS", "120")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "false")

    settings = Settings()

    assert settings.app_name == "devreach-test"
    assert settings.app_env == "test"
    assert settings.debug is True
    assert settings.host == "0.0.0.0"
    assert settings.port == 9000
    assert settings.cors_origins == ["http://one.test", "http://two.test"]
    assert settings.log_level == "DEBUG"
    assert settings.log_max_bytes == 2048
    assert settings.log_backup_count == 2
    assert settings.openai_base_url == "https://api.proxyapi.ru/openai/v1"
    assert settings.contact_rate_limit_requests == 5
    assert settings.contact_rate_limit_window_seconds == 120
    assert settings.trust_proxy_headers is False


@pytest.mark.parametrize(
    ("raw_value", "expected_value"),
    [
        ("true", True),
        ("release", False),
        ("debug", True),
        ("production", False),
    ],
    ids=[
        "debug включается значением true",
        "debug выключается значением release",
        "debug включается значением debug",
        "debug выключается значением production",
    ],
)
def test_debug_value_is_parsed(monkeypatch, raw_value: str, expected_value: bool) -> None:
    """CONFIG-001: значение DEBUG понятно преобразуется в булевый режим."""
    monkeypatch.setenv("DEBUG", raw_value)

    settings = Settings()

    assert settings.debug is expected_value


@pytest.mark.parametrize(
    ("env_name", "env_value"),
    [
        ("CONTACT_RATE_LIMIT_REQUESTS", "0"),
        ("CONTACT_RATE_LIMIT_WINDOW_SECONDS", "0"),
        ("CONTACT_RATE_LIMIT_REQUESTS", "-1"),
        ("CONTACT_RATE_LIMIT_WINDOW_SECONDS", "-1"),
    ],
    ids=[
        "нулевой лимит обращений отклоняется",
        "нулевое окно rate limit отклоняется",
        "отрицательный лимит обращений отклоняется",
        "отрицательное окно rate limit отклоняется",
    ],
)
def test_invalid_rate_limit_settings_are_rejected(monkeypatch, env_name: str, env_value: str) -> None:
    """CONFIG-RATE-LIMIT-001: некорректные настройки rate limiting отклоняются при загрузке."""
    monkeypatch.setenv(env_name, env_value)

    with pytest.raises(ValueError, match="больше нуля"):
        Settings()

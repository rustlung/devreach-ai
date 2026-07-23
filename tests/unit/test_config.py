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

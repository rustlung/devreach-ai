from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def readable_test_id(description: str):
    return pytest.mark.parametrize("_case_id", [None], ids=[description])


@pytest.fixture
def test_settings(tmp_path) -> Settings:
    return Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'test.sqlite3'}",
        LOG_FILE_PATH=str(tmp_path / "test.log"),
        CORS_ORIGINS=["http://testserver"],
    )


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

from pathlib import Path

import pytest
from pydantic import SecretStr

from digestify_api.couchdb import Client, Database, Settings


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Shield the tests from the repo's `.env` file and ambient variables."""
    monkeypatch.chdir(tmp_path)
    for variable in ("COUCHDB_URL", "COUCHDB_USER", "COUCHDB_PASSWORD"):
        monkeypatch.delenv(variable, raising=False)


def test_settings_defaults() -> None:
    settings = Settings()

    assert settings.url == "http://localhost:5984"
    assert settings.user == "admin"
    assert settings.password.get_secret_value() == "password"


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUCHDB_URL", "http://db:5984")
    monkeypatch.setenv("COUCHDB_USER", "service")
    monkeypatch.setenv("COUCHDB_PASSWORD", "hunter2")

    settings = Settings()

    assert settings.url == "http://db:5984"
    assert settings.user == "service"
    assert settings.password.get_secret_value() == "hunter2"


def test_settings_do_not_leak_password_in_repr() -> None:
    settings = Settings(password=SecretStr("hunter2"))

    assert "hunter2" not in repr(settings)
    assert "hunter2" not in str(settings)


async def test_connect_hands_out_databases() -> None:
    settings = Settings(url="http://db:5984")

    async with Client.connect(settings) as couch:
        database = couch.get_database("things")

        assert isinstance(database, Database)
        assert database.name == "things"


async def test_connect_configures_client_from_settings() -> None:
    settings = Settings(url="http://db:5984")

    async with Client.connect(settings) as couch:
        client = couch._http_client

        assert str(client.base_url) == "http://db:5984"
        assert client.timeout.read == 10.0
        assert client.timeout.connect == 10.0
        assert client.timeout.write == 10.0
        assert client.timeout.pool == 10.0

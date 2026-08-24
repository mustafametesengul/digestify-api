from pathlib import Path

import pytest
from pydantic import SecretStr

from digestify_api.couchdb import CouchDB, CouchDBSettings, Database


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Shield the tests from the repo's `.env` file and ambient variables."""
    monkeypatch.chdir(tmp_path)
    for variable in ("COUCHDB_URL", "COUCHDB_USER", "COUCHDB_PASSWORD"):
        monkeypatch.delenv(variable, raising=False)


def test_settings_defaults() -> None:
    settings = CouchDBSettings()

    assert settings.url == "http://localhost:5984"
    assert settings.user == "admin"
    assert settings.password.get_secret_value() == "password"


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUCHDB_URL", "http://db:5984")
    monkeypatch.setenv("COUCHDB_USER", "service")
    monkeypatch.setenv("COUCHDB_PASSWORD", "hunter2")

    settings = CouchDBSettings()

    assert settings.url == "http://db:5984"
    assert settings.user == "service"
    assert settings.password.get_secret_value() == "hunter2"


def test_settings_do_not_leak_password_in_repr() -> None:
    settings = CouchDBSettings(password=SecretStr("hunter2"))

    assert "hunter2" not in repr(settings)
    assert "hunter2" not in str(settings)


async def test_connect_hands_out_databases() -> None:
    settings = CouchDBSettings(url="http://db:5984")

    async with CouchDB.connect(settings) as couch:
        database = couch.get_database("things")

        assert isinstance(database, Database)
        assert database.name == "things"


async def test_connect_configures_client_from_settings() -> None:
    settings = CouchDBSettings(url="http://db:5984")

    async with CouchDB.connect(settings) as couch:
        client = couch._client

        assert str(client.base_url) == "http://db:5984"
        # The read timeout must stay unbounded for continuous changes feeds.
        assert client.timeout.read is None
        assert client.timeout.connect == 10.0

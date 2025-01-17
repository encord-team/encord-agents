import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from encord_agents.core.settings import Settings

from .utils import AuthMode


@pytest.fixture(scope="function")
def setup(request: pytest.FixtureRequest, os_env_key_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = request.node.get_closest_marker("env_mode")
    mode: AuthMode = AuthMode.KEY_CONTENT if marker is None else marker.args[0]

    current_content = os.environ["ENCORD_SSH_KEY"]

    if mode in [AuthMode.KEY_CONTENT, AuthMode.BOTH]:
        monkeypatch.setenv("ENCORD_SSH_KEY", current_content)
    else:
        monkeypatch.delenv("ENCORD_SSH_KEY", raising=False)

    if mode in [AuthMode.KEY_FILE, AuthMode.BOTH]:
        monkeypatch.setenv("ENCORD_SSH_KEY_FILE", os_env_key_file.as_posix())
    else:
        monkeypatch.delenv("ENCORD_SSH_KEY_FILE", raising=False)


@pytest.mark.env_mode(AuthMode.KEY_CONTENT)
def test_auth_strategies_key_content(setup: None) -> None:
    settings = Settings()
    assert settings.ssh_key_content is not None
    assert settings.ssh_key_file is None
    assert settings.ssh_key


@pytest.mark.env_mode(AuthMode.KEY_FILE)
def test_auth_strategies_key_file(setup: None) -> None:
    settings = Settings()
    assert settings.ssh_key_file is not None
    assert settings.ssh_key_content is None
    assert settings.ssh_key


@pytest.mark.env_mode(AuthMode.BOTH)
def test_auth_strategies_key_content_and_file(setup: None) -> None:
    with pytest.warns(
        UserWarning,
        match="You have configured both the `ENCORD_SSH_KEY` and `ENCORD_SSH_KEY_FILE`. The `ENCORD_SSH_KEY` will take precedence.",
    ):
        settings = Settings()
    assert settings.ssh_key_file is not None
    assert settings.ssh_key_content is not None
    assert settings.ssh_key


@pytest.mark.env_mode(AuthMode.NONE)
def test_auth_strategies_none(setup: None) -> None:
    with pytest.raises(ValidationError):
        Settings()


def test_auth_stragies_with_default_env() -> None:
    settings = Settings()
    assert settings.ssh_key_content is not None
    assert settings.ssh_key_file is None
    assert settings.ssh_key

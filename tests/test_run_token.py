import dataclasses
import json
import uuid
from typing import Callable, Optional
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, request

from encord_agents.aws.wrappers import editor_agent as aws_editor_agent
from encord_agents.core.constants import AGENT_RUN_TOKEN_HEADER
from encord_agents.core.data_model import FrameData
from encord_agents.core.run_token import current_agent_run_token, forwarding_agent_run_token
from encord_agents.core.utils import get_user_client, get_user_client_from_settings
from encord_agents.gcp.wrappers import editor_agent

BODY = {"projectHash": str(uuid.uuid4()), "dataHash": str(uuid.uuid4()), "frame": 0}


def _call(headers: dict[str, str]) -> list[Optional[str]]:
    seen: list[Optional[str]] = []

    @editor_agent()
    def agent(frame_data: FrameData) -> None:
        seen.append(current_agent_run_token())

    with patch("encord_agents.gcp.wrappers.get_user_client", return_value=MagicMock()):
        with Flask(__name__).test_request_context("/", method="POST", json=BODY, headers=headers):
            agent(request)
    return seen


@pytest.mark.parametrize("name", [AGENT_RUN_TOKEN_HEADER, AGENT_RUN_TOKEN_HEADER.lower()])
def test_the_token_is_available_during_the_call(name: str) -> None:
    assert _call({name: "opaque-token"}) == ["opaque-token"]
    assert current_agent_run_token() is None


def test_no_header_means_nothing_to_forward() -> None:
    assert _call({}) == [None]


def test_blank_values_are_not_forwarded() -> None:
    with forwarding_agent_run_token("  "):
        assert current_agent_run_token() is None


@dataclasses.dataclass
class _RequestsSettings:
    trace_id_provider: Optional[Callable[[], str]] = None
    agent_run_token_provider: Optional[Callable[[], Optional[str]]] = None


@dataclasses.dataclass
class _OlderRequestsSettings:
    trace_id_provider: Optional[Callable[[], str]] = None


def test_the_client_forwards_the_token_when_the_sdk_supports_it() -> None:
    client = MagicMock()
    client._config.requests_settings = _RequestsSettings()
    with patch("encord_agents.core.utils.get_user_client_from_settings", return_value=client):
        get_user_client(MagicMock())
    assert client._config.requests_settings.agent_run_token_provider is current_agent_run_token


def test_the_client_is_untouched_with_an_older_sdk() -> None:
    client = MagicMock()
    client._config.requests_settings = _OlderRequestsSettings()
    with patch("encord_agents.core.utils.get_user_client_from_settings", return_value=client):
        get_user_client(MagicMock())
    assert dataclasses.asdict(client._config.requests_settings) == {"trace_id_provider": None}


def test_the_cached_client_has_its_own_requests_settings() -> None:
    from encord.http.constants import DEFAULT_REQUESTS_SETTINGS

    get_user_client_from_settings.cache_clear()
    with patch("encord_agents.core.utils.EncordUserClient.create_with_ssh_private_key") as create:
        get_user_client_from_settings(MagicMock(domain=None, ssh_key="key"))
    requests_settings = create.call_args.kwargs["requests_settings"]
    assert requests_settings is not DEFAULT_REQUESTS_SETTINGS
    assert requests_settings == DEFAULT_REQUESTS_SETTINGS
    get_user_client_from_settings.cache_clear()


def _aws_call(headers: Optional[dict[str, str]]) -> list[Optional[str]]:
    seen: list[Optional[str]] = []

    @aws_editor_agent()
    def agent(frame_data: FrameData) -> None:
        seen.append(current_agent_run_token())

    event: dict[str, object] = {"body": json.dumps(BODY)}
    if headers is not None:
        event["headers"] = headers
    with patch("encord_agents.aws.wrappers.get_user_client", return_value=MagicMock()):
        agent(event, None)
    return seen


@pytest.mark.parametrize("name", [AGENT_RUN_TOKEN_HEADER, AGENT_RUN_TOKEN_HEADER.lower()])
def test_aws_makes_the_token_available_during_the_call(name: str) -> None:
    assert _aws_call({name: "opaque-token"}) == ["opaque-token"]
    assert current_agent_run_token() is None


@pytest.mark.parametrize("headers", [{}, None], ids=["no-token", "no-headers"])
def test_aws_calls_without_a_token_are_unchanged(headers: Optional[dict[str, str]]) -> None:
    assert _aws_call(headers) == [None]

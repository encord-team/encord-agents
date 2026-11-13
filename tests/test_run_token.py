import dataclasses
import subprocess
import sys
import time
import uuid
from typing import Any, Callable, Optional
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from flask import Flask, Response, request

import encord_agents.core.run_token as run_token_module
from encord_agents.core.constants import AGENT_RUN_TOKEN_HEADER, EDITOR_TEST_REQUEST_HEADER
from encord_agents.core.data_model import FrameData
from encord_agents.core.run_token import (
    AgentRunTokenMode,
    AgentRunTokenSettings,
    current_agent_run_token,
    verify_agent_run_token,
)
from encord_agents.core.utils import get_user_client
from encord_agents.gcp.wrappers import editor_agent

ISSUER = "https://api.example.com"
_REAL_JWKS_CLIENT = run_token_module._jwks_client
KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())
ORGANISATION_UUID = uuid.uuid4()
PROJECT_HASH = uuid.uuid4()
DATA_HASH = uuid.uuid4()
FRAME_DATA = FrameData.model_validate({"projectHash": str(PROJECT_HASH), "dataHash": str(DATA_HASH), "frame": 3})
BODY = {"projectHash": str(PROJECT_HASH), "dataHash": str(DATA_HASH), "frame": 3}


def _token(key: ec.EllipticCurvePrivateKey = KEY, **overrides: Any) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": ["https://agent.example.com", ISSUER],
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "jti": "run-1",
        "token_use": "editor_agent_run",
        "organisation_uuid": str(ORGANISATION_UUID),
        "project_hash": str(PROJECT_HASH),
        "data_hash": str(DATA_HASH),
        "frame": 3,
        **overrides,
    }
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "k"})


@pytest.fixture(autouse=True)
def _keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCORD_DOMAIN", ISSUER)
    for name in [
        "ENCORD_AGENT_RUN_TOKEN_MODE",
        "ENCORD_AGENT_RUN_TOKEN_ISSUER",
        "ENCORD_AGENT_RUN_TOKEN_JWKS_URL",
        "ENCORD_AGENT_RUN_TOKEN_ORGANISATIONS",
    ]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("ENCORD_AGENT_RUN_TOKEN_AUDIENCES", raising=False)

    jwks_client = MagicMock()
    jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key=KEY.public_key())
    monkeypatch.setattr("encord_agents.core.run_token._jwks_client", lambda url: jwks_client)


def _settings(**values: Any) -> AgentRunTokenSettings:
    return AgentRunTokenSettings(**values)


def test_defaults_come_from_encord_domain() -> None:
    settings = _settings()
    assert settings.mode is AgentRunTokenMode.OFF
    assert settings.expected_issuer == ISSUER
    assert settings.keys_url == f"{ISSUER}/v2/public/agents/run-token/jwks"


def test_keys_url_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCORD_AGENT_RUN_TOKEN_JWKS_URL", "https://keys.example.com/jwks")
    assert _settings().keys_url == "https://keys.example.com/jwks"


def test_a_genuine_token_verifies() -> None:
    check = verify_agent_run_token(_token(), FRAME_DATA, _settings())
    assert check.verified
    assert check.claims["jti"] == "run-1"


@pytest.mark.parametrize(
    ("token", "failure"),
    [
        pytest.param(None, "no run token", id="missing"),
        pytest.param(_token(token_use="other"), "not an editor agent run token", id="other-purpose"),
        pytest.param(_token(project_hash=str(uuid.uuid4())), "different project_hash", id="other-project"),
        pytest.param(_token(frame=4), "different frame", id="other-frame"),
        pytest.param(_token(iss="https://other.example.com"), "InvalidIssuerError", id="other-issuer"),
        pytest.param(_token(exp=int(time.time()) - 120), "ExpiredSignatureError", id="expired"),
    ],
)
def test_bad_tokens_do_not_verify(token: Optional[str], failure: str) -> None:
    check = verify_agent_run_token(token, FRAME_DATA, _settings())
    assert not check.verified
    assert check.failure is not None and failure in check.failure


def test_a_token_signed_by_another_key_does_not_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    check = verify_agent_run_token(_token(key=OTHER_KEY), FRAME_DATA, _settings())
    assert not check.verified


def test_configured_audiences_refuse_tokens_for_other_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCORD_AGENT_RUN_TOKEN_AUDIENCES", "https://my-agent.example.com")
    check = verify_agent_run_token(_token(), FRAME_DATA, _settings())
    assert not check.verified


AGENT_URL = "https://agent.example.com"


def _call(
    headers: dict[str, str],
    mode: Optional[AgentRunTokenMode] = None,
    audiences: Optional[list[str]] = None,
) -> tuple[Response, list[Optional[str]], MagicMock]:
    seen: list[Optional[str]] = []
    if mode is AgentRunTokenMode.ENFORCE and audiences is None:
        audiences = [AGENT_URL]

    @editor_agent(agent_run_token_mode=mode, agent_run_token_audiences=audiences)
    def agent(frame_data: FrameData) -> None:
        seen.append(current_agent_run_token())

    client = MagicMock()
    with patch("encord_agents.gcp.wrappers.get_user_client", return_value=client):
        with Flask(__name__).test_request_context("/", method="POST", json=BODY, headers=headers):
            response = agent(request)
    return response, seen, client


def test_off_by_default_runs_without_checking() -> None:
    with patch("encord_agents.gcp.wrappers.check_agent_run_token") as check:
        response, seen, _ = _call({AGENT_RUN_TOKEN_HEADER: _token()})
    check.assert_not_called()
    assert response.status_code == 200
    assert seen == [None]


def test_the_mode_can_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCORD_AGENT_RUN_TOKEN_MODE", "enforce")
    monkeypatch.setenv("ENCORD_AGENT_RUN_TOKEN_AUDIENCES", AGENT_URL)
    response, seen, _ = _call({})
    assert response.status_code == 401
    assert seen == []


@pytest.mark.parametrize("headers", [{}, {AGENT_RUN_TOKEN_HEADER: _token(key=OTHER_KEY)}], ids=["missing", "invalid"])
def test_warn_runs_the_agent_without_forwarding(headers: dict[str, str]) -> None:
    response, seen, _ = _call(headers, mode=AgentRunTokenMode.WARN)
    assert response.status_code == 200
    assert seen == [None]


@pytest.mark.parametrize("headers", [{}, {AGENT_RUN_TOKEN_HEADER: _token(key=OTHER_KEY)}], ids=["missing", "invalid"])
def test_enforce_refuses_without_running_the_agent(headers: dict[str, str]) -> None:
    response, seen, client = _call(headers, mode=AgentRunTokenMode.ENFORCE)
    assert response.status_code == 401
    assert seen == []
    client.get_project.assert_not_called()


@pytest.mark.parametrize("mode", [AgentRunTokenMode.WARN, AgentRunTokenMode.ENFORCE])
def test_a_verified_token_is_available_only_during_the_run(mode: AgentRunTokenMode) -> None:
    token = _token()
    response, seen, _ = _call({AGENT_RUN_TOKEN_HEADER: token}, mode=mode)
    assert response.status_code == 200
    assert seen == [token]
    assert current_agent_run_token() is None


def test_enforce_without_audiences_fails_at_startup() -> None:
    with pytest.raises(ValueError, match="ENCORD_AGENT_RUN_TOKEN_AUDIENCES"):
        _call({}, mode=AgentRunTokenMode.ENFORCE, audiences=[])


@pytest.mark.parametrize(
    ("audiences", "status"),
    [
        pytest.param([AGENT_URL], 200, id="this-agent"),
        pytest.param(["https://other-agent.example.com"], 401, id="other-agent"),
    ],
)
def test_audiences_can_be_passed_to_the_decorator(audiences: list[str], status: int) -> None:
    response, _, _ = _call({AGENT_RUN_TOKEN_HEADER: _token()}, mode=AgentRunTokenMode.ENFORCE, audiences=audiences)
    assert response.status_code == status


def test_editor_test_requests_are_not_checked() -> None:
    response, seen, _ = _call({EDITOR_TEST_REQUEST_HEADER: "test-request"}, mode=AgentRunTokenMode.ENFORCE)
    assert response.status_code == 200
    assert seen == []


@dataclasses.dataclass
class _RequestsSettings:
    trace_id_provider: Optional[Callable[[], str]] = None
    agent_run_token_provider: Optional[Callable[[], Optional[str]]] = None


def test_the_client_forwards_the_current_token_when_the_sdk_supports_it() -> None:
    client = MagicMock()
    client._config.requests_settings = _RequestsSettings()
    with patch("encord_agents.core.utils.get_user_client_from_settings", return_value=client):
        get_user_client(MagicMock())
    assert client._config.requests_settings.agent_run_token_provider is current_agent_run_token


@dataclasses.dataclass
class _OlderRequestsSettings:
    trace_id_provider: Optional[Callable[[], str]] = None


def test_the_client_is_untouched_with_an_older_sdk() -> None:
    client = MagicMock()
    client._config.requests_settings = _OlderRequestsSettings()
    with patch("encord_agents.core.utils.get_user_client_from_settings", return_value=client):
        get_user_client(MagicMock())
    assert dataclasses.asdict(client._config.requests_settings) == {"trace_id_provider": None}


def test_importing_the_library_does_not_load_jwt() -> None:
    script = (
        "import sys\n"
        "import encord_agents.core.utils, encord_agents.gcp.wrappers\n"
        "from encord_agents.gcp.wrappers import editor_agent\n"
        "editor_agent()(lambda frame_data: None)\n"
        "assert 'jwt' not in sys.modules, 'jwt imported'\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(("value", "mode"), [("", "off"), ("  ", "off"), ("WARN", "warn"), (" Enforce ", "enforce")])
def test_the_mode_tolerates_empty_padded_and_upper_case_values(
    monkeypatch: pytest.MonkeyPatch, value: str, mode: str
) -> None:
    monkeypatch.setenv("ENCORD_AGENT_RUN_TOKEN_MODE", value)
    assert _settings().mode is AgentRunTokenMode(mode)


def test_an_unknown_mode_still_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCORD_AGENT_RUN_TOKEN_MODE", "strict")
    with pytest.raises(ValueError):
        _settings()


def test_the_header_name_is_case_insensitive() -> None:
    token = _token()
    response, seen, _ = _call({AGENT_RUN_TOKEN_HEADER.lower(): token}, mode=AgentRunTokenMode.ENFORCE)
    assert response.status_code == 200
    assert seen == [token]


def test_warn_without_audiences_checks_only_the_issuer() -> None:
    token = _token(aud=["https://other-agent.example.com", ISSUER])
    response, seen, _ = _call({AGENT_RUN_TOKEN_HEADER: token}, mode=AgentRunTokenMode.WARN)
    assert response.status_code == 200
    assert seen == [token]


def test_enforce_with_an_invalid_body_does_not_run_the_agent() -> None:
    ran: list[bool] = []

    @editor_agent(agent_run_token_mode=AgentRunTokenMode.ENFORCE, agent_run_token_audiences=[AGENT_URL])
    def agent(frame_data: FrameData) -> None:
        ran.append(True)

    client = MagicMock()
    with patch("encord_agents.gcp.wrappers.get_user_client", return_value=client):
        with Flask(__name__).test_request_context("/", method="POST", json={"projectHash": "not-a-uuid"}):
            with pytest.raises(Exception):
                agent(request)
    assert ran == []
    client.get_project.assert_not_called()


def _use_real_key_fetching(monkeypatch: pytest.MonkeyPatch, keys: list[dict[str, Any]]) -> None:
    _REAL_JWKS_CLIENT.cache_clear()
    monkeypatch.setattr("encord_agents.core.run_token._jwks_client", _REAL_JWKS_CLIENT)
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: {"keys": keys})


def _public_jwk(key: ec.EllipticCurvePrivateKey) -> dict[str, Any]:
    jwk: dict[str, Any] = jwt.algorithms.ECAlgorithm.to_jwk(key.public_key(), as_dict=True)
    return {**jwk, "kid": "k", "alg": "ES256", "use": "sig"}


def test_a_genuine_token_verifies_against_a_fetched_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_real_key_fetching(monkeypatch, [_public_jwk(KEY)])
    assert verify_agent_run_token(_token(), FRAME_DATA, _settings()).verified


def test_an_empty_key_set_does_not_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_real_key_fetching(monkeypatch, [])
    assert not verify_agent_run_token(_token(), FRAME_DATA, _settings()).verified


def test_other_algorithms_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_real_key_fetching(monkeypatch, [_public_jwk(KEY)])
    token = jwt.encode({"iss": ISSUER}, "s" * 32, algorithm="HS256", headers={"kid": "k"})
    assert not verify_agent_run_token(token, FRAME_DATA, _settings()).verified


def test_the_cached_client_has_its_own_requests_settings() -> None:
    from encord.http.constants import DEFAULT_REQUESTS_SETTINGS

    from encord_agents.core.utils import get_user_client_from_settings

    get_user_client_from_settings.cache_clear()
    with patch("encord_agents.core.utils.EncordUserClient.create_with_ssh_private_key") as create:
        get_user_client_from_settings(MagicMock(domain=None, ssh_key="key"))
    requests_settings = create.call_args.kwargs["requests_settings"]
    assert requests_settings is not DEFAULT_REQUESTS_SETTINGS
    assert requests_settings == DEFAULT_REQUESTS_SETTINGS
    get_user_client_from_settings.cache_clear()


def test_tokens_verify_for_a_listed_organisation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCORD_AGENT_RUN_TOKEN_ORGANISATIONS", f"{uuid.uuid4()}, {str(ORGANISATION_UUID).upper()}")
    assert verify_agent_run_token(_token(), FRAME_DATA, _settings()).verified


def test_tokens_for_other_organisations_do_not_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCORD_AGENT_RUN_TOKEN_ORGANISATIONS", str(uuid.uuid4()))
    check = verify_agent_run_token(_token(), FRAME_DATA, _settings())
    assert not check.verified
    assert check.failure is not None and "organisation" in check.failure


def test_organisations_can_be_passed_to_the_decorator() -> None:
    seen: list[Optional[str]] = []

    @editor_agent(
        agent_run_token_mode=AgentRunTokenMode.ENFORCE,
        agent_run_token_audiences=[AGENT_URL],
        agent_run_token_organisations=[str(uuid.uuid4())],
    )
    def agent(frame_data: FrameData) -> None:
        seen.append(current_agent_run_token())

    with patch("encord_agents.gcp.wrappers.get_user_client", return_value=MagicMock()):
        with Flask(__name__).test_request_context(
            "/", method="POST", json=BODY, headers={AGENT_RUN_TOKEN_HEADER: _token()}
        ):
            response = agent(request)
    assert response.status_code == 401
    assert seen == []

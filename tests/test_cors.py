import inspect
import re
import typing

import pytest
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from encord_agents.core.constants import EDITOR_TEST_REQUEST_HEADER, ENCORD_DOMAIN_REGEX
from encord_agents.fastapi.cors import EncordCORSMiddleware, get_encord_app


@pytest.fixture
def legal_origins() -> list[str]:
    return [
        # Example development previews
        "https://cord-ai-development--eb393d03-pccc0hqn.web.app",
        "https://cord-ai-development--40816cb1-dij7k5yt.web.app",
        "https://cord-ai-development--a3353fa9-0wf42o8h.web.app",
        # Main deployment,
        "https://app.encord.com",
        "https://dev.encord.com",
        "https://staging.encord.com",
        # US Deployments,
        "https://staging.us.encord.com",
        "https://dev.us.encord.com",
        "https://app.us.encord.com",
    ]


@pytest.fixture
def illegal_origins() -> list[str]:
    return [
        "https://google.com",
        "https://test.encord.com",
        "https://us.app.encord.com",
        "https://app.encord.com.something-else.com",
        "https://dev.encord.com.something-else.com",
        "https://staging.encord.com.something-else.com",
    ]


@pytest.fixture
def compiled_regex() -> re.Pattern[str]:
    return re.compile(ENCORD_DOMAIN_REGEX)


def test_legal_domains_against_CORS_regex(legal_origins: list[str], compiled_regex: re.Pattern[str]) -> None:
    for origin in legal_origins:
        assert compiled_regex.fullmatch(origin), f"Origin should have been allowed: `{origin}`"


def test_illegal_domains_against_CORS_regex(illegal_origins: list[str], compiled_regex: re.Pattern[str]) -> None:
    for origin in illegal_origins:
        assert not compiled_regex.fullmatch(origin), f"Origin should _not_ have been allowed: `{origin}`"


async def _noop_app(scope: Scope, receive: Receive, send: Send) -> None:
    """Minimal ASGI app, only used to instantiate the middleware."""


def test_cors_middleware_binds_arguments_correctly() -> None:
    """Regression test for https://github.com/encord-team/encord-agents/issues/201.

    Starlette 0.51.0 added an `allow_private_network` parameter in the middle of the
    `CORSMiddleware.__init__` signature. Forwarding our arguments positionally shifted
    `expose_headers` and `max_age` onto the wrong parameters, which made the middleware
    raise `TypeError: can only join an iterable` on construction.
    """
    middleware = EncordCORSMiddleware(_noop_app, expose_headers=("X-Custom-Header",), max_age=1234)

    assert middleware.allow_origin_regex is not None
    assert middleware.allow_origin_regex.pattern == ENCORD_DOMAIN_REGEX
    assert "POST" in middleware.allow_methods
    assert middleware.simple_headers["Access-Control-Expose-Headers"] == "X-Custom-Header"
    assert middleware.preflight_headers["Access-Control-Max-Age"] == "1234"


def test_cors_middleware_preflight_response() -> None:
    app = get_encord_app()

    @app.post("/")
    def post_root() -> None:
        return None

    client = TestClient(app)
    response = client.options(
        "/",
        headers={
            "Origin": "https://app.encord.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": EDITOR_TEST_REQUEST_HEADER,
        },
    )

    assert response.status_code == 200, response.content
    assert response.headers["Access-Control-Allow-Origin"] == "https://app.encord.com"
    assert response.headers["Access-Control-Max-Age"] == "3600"
    assert EDITOR_TEST_REQUEST_HEADER.lower() in response.headers["Access-Control-Allow-Headers"].lower()


def test_cors_middleware_forwards_no_positional_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard the mechanism, not just the symptom, of issue #201.

    Positional forwarding only misbehaves against a Starlette version whose
    `CORSMiddleware.__init__` gained a parameter, so a test asserting on the
    constructed middleware passes on old Starlette even with the bug present.
    Asserting that nothing is forwarded positionally fails on every version.
    """
    recorded: dict[str, typing.Any] = {}

    def recording_init(self: CORSMiddleware, app: ASGIApp, *args: typing.Any, **kwargs: typing.Any) -> None:
        recorded["args"] = args
        recorded["kwargs"] = kwargs

    monkeypatch.setattr(CORSMiddleware, "__init__", recording_init)
    EncordCORSMiddleware(_noop_app, expose_headers=("X-Custom-Header",), max_age=1234)

    assert recorded["args"] == (), (
        "Arguments must be forwarded to CORSMiddleware by keyword: positional forwarding silently "
        "shifts onto the wrong parameters whenever Starlette inserts a new one."
    )
    assert recorded["kwargs"]["expose_headers"] == ("X-Custom-Header",)
    assert recorded["kwargs"]["max_age"] == 1234


def test_forwarded_argument_names_exist_in_starlette_signature() -> None:
    """Keyword forwarding breaks if Starlette ever renames a parameter, so check the names."""
    starlette_parameters = set(inspect.signature(CORSMiddleware.__init__).parameters)
    forwarded = set(inspect.signature(EncordCORSMiddleware.__init__).parameters) - {"self", "app", "kwargs"}

    missing = sorted(forwarded - starlette_parameters)
    assert not missing, f"Arguments no longer accepted by Starlette's CORSMiddleware: {missing}"

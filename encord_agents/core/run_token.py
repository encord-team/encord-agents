"""
Verify the agent run token Encord sends with editor agent calls.

The token is a short-lived ES256 JWT, sent in the `X-Encord-Agent-Run-Token` header. It
says which project, data unit and frame the run is for, and can be checked against the
public keys of the Encord deployment the agent is configured for.

Checking is off by default. Set `ENCORD_AGENT_RUN_TOKEN_MODE`:

- `off`: no checks.
- `warn`: check every call and log the outcome, but always run the agent.
- `enforce`: refuse calls without a valid token. Needs `ENCORD_AGENT_RUN_TOKEN_AUDIENCES`.

Set `ENCORD_AGENT_RUN_TOKEN_ORGANISATIONS` to accept only tokens for the organisations this
agent serves.
"""

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Iterator, Mapping, Optional, Sequence

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from encord_agents.core.constants import AGENT_RUN_TOKEN_HEADER
from encord_agents.core.data_model import FrameData

if TYPE_CHECKING:
    import jwt

logger = logging.getLogger(__name__)

DEFAULT_ENCORD_DOMAIN = "https://api.encord.com"
JWKS_PATH = "/v2/public/agents/run-token/jwks"
TOKEN_USE = "editor_agent_run"

_LEEWAY_SECONDS = 30
_JWKS_TIMEOUT_SECONDS = 5
_JWKS_CACHE_SECONDS = 300


class AgentRunTokenMode(str, Enum):
    OFF = "off"
    WARN = "warn"
    ENFORCE = "enforce"


class AgentRunTokenSettings(BaseSettings):
    """Settings for checking agent run tokens, read from environment variables."""

    mode: AgentRunTokenMode = Field(validation_alias="ENCORD_AGENT_RUN_TOKEN_MODE", default=AgentRunTokenMode.OFF)
    domain: Optional[str] = Field(validation_alias="ENCORD_DOMAIN", default=None)
    issuer: Optional[str] = Field(validation_alias="ENCORD_AGENT_RUN_TOKEN_ISSUER", default=None)
    """The expected issuer. Defaults to `ENCORD_DOMAIN`, or https://api.encord.com."""
    jwks_url: Optional[str] = Field(validation_alias="ENCORD_AGENT_RUN_TOKEN_JWKS_URL", default=None)
    """Where to fetch the public keys. Defaults to the issuer's key set."""
    audiences: Optional[str] = Field(validation_alias="ENCORD_AGENT_RUN_TOKEN_AUDIENCES", default=None)
    """
    Comma-separated addresses this agent is registered under, checked against the token's
    audience. Required in `enforce` mode.
    """
    organisations: Optional[str] = Field(validation_alias="ENCORD_AGENT_RUN_TOKEN_ORGANISATIONS", default=None)
    """
    Comma-separated Encord organisation UUIDs this agent serves. When set, tokens for other
    organisations do not verify.
    """

    @field_validator("mode", mode="before")
    @classmethod
    def normalise_mode(cls, value: Any) -> Any:
        # Tolerate the shapes deploy templates produce: empty, padded or upper-case.
        if isinstance(value, str):
            value = value.strip().lower()
            return value or AgentRunTokenMode.OFF
        return value

    @classmethod
    def resolve(
        cls,
        mode: Optional[AgentRunTokenMode] = None,
        audiences: Optional[Sequence[str]] = None,
        organisations: Optional[Sequence[str]] = None,
    ) -> "AgentRunTokenSettings":
        """Read the environment, apply explicit overrides, and check the result is usable."""
        settings = cls()
        overrides: dict[str, Any] = {}
        if mode is not None:
            overrides["mode"] = AgentRunTokenMode(mode)
        if audiences is not None:
            overrides["audiences"] = ",".join(audiences)
        if organisations is not None:
            overrides["organisations"] = ",".join(str(organisation) for organisation in organisations)
        if overrides:
            settings = settings.model_copy(update=overrides)
        if settings.mode is AgentRunTokenMode.ENFORCE and not settings.configured_audiences:
            raise ValueError(
                "Agent run token mode `enforce` needs the agent's own address as audience: set "
                "`ENCORD_AGENT_RUN_TOKEN_AUDIENCES` or pass `agent_run_token_audiences`."
            )
        return settings

    @property
    def configured_audiences(self) -> list[str]:
        return [value.strip() for value in (self.audiences or "").split(",") if value.strip()]

    @property
    def configured_organisations(self) -> set[str]:
        return {value.strip().lower() for value in (self.organisations or "").split(",") if value.strip()}

    @property
    def expected_issuer(self) -> str:
        return (self.issuer or self.domain or DEFAULT_ENCORD_DOMAIN).rstrip("/")

    @property
    def keys_url(self) -> str:
        return self.jwks_url or f"{self.expected_issuer}{JWKS_PATH}"

    @property
    def expected_audiences(self) -> list[str]:
        return self.configured_audiences or [self.expected_issuer]


@dataclass(frozen=True)
class AgentRunTokenCheck:
    """The outcome of checking one call's run token."""

    mode: AgentRunTokenMode
    token: Optional[str] = None
    """The verified token. None unless verification passed."""
    claims: dict[str, Any] = field(default_factory=dict)
    failure: Optional[str] = None
    """Why verification failed, if it did."""

    @property
    def verified(self) -> bool:
        return self.token is not None

    @property
    def refused(self) -> bool:
        return self.mode is AgentRunTokenMode.ENFORCE and not self.verified


_current_token: ContextVar[Optional[str]] = ContextVar("encord_agent_run_token", default=None)


def current_agent_run_token() -> Optional[str]:
    """The verified run token of the call being handled, if any."""
    return _current_token.get()


@contextmanager
def forwarding_agent_run_token(check: AgentRunTokenCheck) -> Iterator[None]:
    """While inside, Encord SDK calls made through `get_user_client` send the verified token."""
    reset = _current_token.set(check.token)
    try:
        yield
    finally:
        _current_token.reset(reset)


@lru_cache(maxsize=8)
def _jwks_client(url: str) -> "jwt.PyJWKClient":
    import jwt

    # The key set is cached for `lifespan`; individual keys are not cached separately, so a
    # key removed from the set stops verifying once the cache expires.
    return jwt.PyJWKClient(url, lifespan=_JWKS_CACHE_SECONDS, timeout=_JWKS_TIMEOUT_SECONDS)


def _mismatched_fields(claims: Mapping[str, Any], frame_data: FrameData) -> list[str]:
    expected = {
        "project_hash": str(frame_data.project_hash),
        "data_hash": str(frame_data.data_hash),
        "frame": str(frame_data.frame),
    }
    return [name for name, value in expected.items() if str(claims.get(name)).lower() != value.lower()]


def verify_agent_run_token(
    token: Optional[str], frame_data: FrameData, settings: AgentRunTokenSettings
) -> AgentRunTokenCheck:
    """Verify a run token for this call, without logging."""
    import jwt  # Imported only when checking is on.

    if not token:
        return AgentRunTokenCheck(mode=settings.mode, failure="no run token on the request")
    try:
        signing_key = _jwks_client(settings.keys_url).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["ES256"],
            issuer=settings.expected_issuer,
            audience=settings.expected_audiences,
            leeway=_LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "nbf", "iss", "aud", "jti"]},
        )
    except jwt.PyJWTError as exc:
        return AgentRunTokenCheck(mode=settings.mode, failure=f"invalid run token: {type(exc).__name__}: {exc}")

    if claims.get("token_use") != TOKEN_USE:
        return AgentRunTokenCheck(mode=settings.mode, failure="not an editor agent run token")
    organisations = settings.configured_organisations
    if organisations and str(claims.get("organisation_uuid")).lower() not in organisations:
        return AgentRunTokenCheck(
            mode=settings.mode, failure="run token is for an organisation this agent does not serve"
        )
    mismatched = _mismatched_fields(claims, frame_data)
    if mismatched:
        return AgentRunTokenCheck(
            mode=settings.mode, failure=f"run token is for a different {', '.join(mismatched)} than the request"
        )
    return AgentRunTokenCheck(mode=settings.mode, token=token, claims=claims)


def check_agent_run_token(
    token: Optional[str], frame_data: FrameData, settings: AgentRunTokenSettings
) -> AgentRunTokenCheck:
    """
    Verify a call's run token, taken from the `X-Encord-Agent-Run-Token` header, and log the
    outcome. The token itself is never logged.
    """
    check = verify_agent_run_token(token, frame_data, settings)
    if check.verified:
        logger.info(
            "Agent run token verified: run_id=%s project_hash=%s",
            check.claims.get("jti"),
            check.claims.get("project_hash"),
        )
    else:
        outcome = "refusing the call" if check.refused else "running without it"
        logger.warning("Agent run token not verified (%s): %s", outcome, check.failure)
    return check

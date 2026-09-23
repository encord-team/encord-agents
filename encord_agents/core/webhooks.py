"""Verifying and reading the requests Encord signs.

Encord signs every request it makes to a configured URL: the task-ready notifications
an agent stage sends, and the calls it makes to a custom agent endpoint. Those URLs
have to be publicly reachable, so the signature is what separates a genuine request
from anything else that finds them.

Verification needs the signing secret, which Encord shows in the app alongside the
endpoint's configuration. Set it as `ENCORD_WEBHOOK_SECRET`, or pass it explicitly, and
check it again if you change that configuration.
"""

import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator

from encord_agents.core.constants import WEBHOOK_SIGNATURE_HEADER, WEBHOOK_TIMESTAMP_HEADER
from encord_agents.core.settings import WebhookSettings
from encord_agents.exceptions import PrintableError

DEFAULT_TIMESTAMP_TOLERANCE_SECONDS = 300
"""How far the signed timestamp may be from now before a request is refused as a replay."""

AGENT_STAGE_WORK_AVAILABLE_EVENT = "agent_stage_work_available_event"
"""The event Encord sends when tasks are waiting at an agent stage."""

SUPPORTED_NOTIFICATION_VERSION = 1
"""The envelope version this module reads.

Encord bumps it only for a change that breaks the previous shape; fields and enum
values are added without one. So an envelope on this version is safe to read even if
it carries things this module has never heard of, and one on another version is not.
"""


class WebhookVerificationError(Exception):
    """A request could not be shown to have come from Encord.

    Treat it as hostile: do not read the body, and answer with a 4xx.
    """


class UnexpectedEventType(Exception):
    """The request is genuine, but carries an event this module does not read.

    A single URL can be configured on more than one workflow stage, so a receiver
    written for agent-stage notifications can legitimately be sent, say, a
    `task_submitted_event`. Acknowledge those rather than failing on them.
    """

    def __init__(self, event_type: str) -> None:
        super().__init__(f"Expected event `{AGENT_STAGE_WORK_AVAILABLE_EVENT}`, got `{event_type}`.")
        self.event_type = event_type


class UnsupportedNotificationVersion(Exception):
    """The request is genuine, but its envelope is a version this module cannot read.

    Encord reserves a version bump for a breaking change, so the payload cannot be
    read as the version below. Upgrade `encord-agents`.
    """

    def __init__(self, version: Any) -> None:
        super().__init__(
            f"Notification is version {version}; this version of `encord-agents` reads "
            f"version {SUPPORTED_NOTIFICATION_VERSION}. Upgrade the package to read it."
        )
        self.version = version


class AgentStageWorkReason(str, Enum):
    """Which condition made Encord send the notification."""

    BATCH_SIZE_REACHED = "batch_size_reached"
    """The number of queued tasks reached the stage's minimum batch size."""
    MAX_WAIT_ELAPSED = "max_wait_elapsed"
    """A task had been queued longer than the stage's maximum wait."""

    def __str__(self) -> str:
        # Without this a member formats as `AgentStageWorkReason.BATCH_SIZE_REACHED`,
        # so a log line would render a known condition differently from one this
        # version has never heard of, which arrives as the wire string itself.
        return str.__str__(self)


class StageWorkAvailable(BaseModel):
    """What the notification says about the stage."""

    project_hash: UUID
    stage_uuid: UUID
    pending_count: int
    """How many tasks were queued when the notification was raised.

    A hint, not a promise: fetch the queue to find what is actually there now.
    """
    reason: AgentStageWorkReason | str
    """Which condition fired.

    A condition added platform-side arrives as a plain string rather than failing
    validation, since Encord adds those without bumping the envelope version. Compare
    against `AgentStageWorkReason` for the ones known here -- and to tell a known one
    from a new one, use `isinstance(reason, AgentStageWorkReason)`, since the enum
    subclasses `str` and so is a `str` either way.
    """

    @field_validator("reason", mode="before")
    @classmethod
    def _keep_unknown_reason(cls, value: Any) -> Any:
        try:
            return AgentStageWorkReason(value)
        except ValueError:
            return value


class TaskNotification(BaseModel):
    """Tasks are waiting at an agent stage.

    Carries no task data. Act on it by fetching that stage's queue, which may by then
    hold more, fewer or none of the tasks the notification counted.
    """

    uid: UUID
    """Identifies this delivery. Not a deduplication key: Encord recomputes the state
    every cycle and re-notifies with a fresh uid while work remains."""
    version: int
    source: str
    event_type: str
    event_created_timestamp: datetime
    payload: StageWorkAvailable

    @property
    def project_hash(self) -> UUID:
        return self.payload.project_hash

    @property
    def stage_uuid(self) -> UUID:
        return self.payload.stage_uuid

    @property
    def pending_count(self) -> int:
        return self.payload.pending_count

    @property
    def reason(self) -> AgentStageWorkReason | str:
        return self.payload.reason


def _read_header(headers: Mapping[str, str], name: str) -> str | None:
    """Read a header regardless of case.

    Header names are case-insensitive, but not every framework hands them over in a
    mapping that knows that -- an AWS Lambda event, for one, is a plain lowercased dict.
    """
    exact = headers.get(name)
    if exact is not None:
        return exact
    wanted = name.lower()
    return next((value for key, value in headers.items() if key.lower() == wanted), None)


def _unreadable_signature_headers(headers: Mapping[str, str]) -> list[str]:
    """Signature headers on the request that this version of the package cannot read.

    Encord may add a signature header alongside `X-Encord-Signature` and retire that
    one after a grace period. A version released before the new header exists has no
    way to verify against it, but it can name it -- so that the request reads as one
    this package is too old for, rather than as an unsigned request, and the fix reads
    as "upgrade" rather than "check your secret".
    """
    known = WEBHOOK_SIGNATURE_HEADER.lower()
    return sorted(key for key in headers if key.lower().startswith(known) and key.lower() != known)


def _resolve_secret(secret: str | None) -> str:
    """Use the secret given, else the one in the environment."""
    resolved = secret or WebhookSettings().webhook_secret
    if not resolved:
        raise PrintableError(
            "No signing secret to verify against. Pass `[blue]secret[/blue]` or set the "
            "`[blue]ENCORD_WEBHOOK_SECRET[/blue]` environment variable to the secret shown "
            "in the Encord app."
        )
    return resolved


def verify_signature(
    body: bytes,
    *,
    signature: str | None,
    timestamp: str | None,
    secret: str | None = None,
    tolerance_seconds: int = DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
) -> None:
    """Check that `body` carries a signature only Encord could have produced.

    Args:
        body: The request body exactly as received. Re-serializing it first will not
            verify -- the signature covers the bytes that were sent.
        signature: The `X-Encord-Signature` header, if present.
        timestamp: The `X-Encord-Timestamp` header, if present.
        secret: The signing secret to verify against. Read from
            `ENCORD_WEBHOOK_SECRET` when not given.
        tolerance_seconds: How far from now the signed timestamp may be.

    Raises:
        WebhookVerificationError: If the headers are missing or malformed, the timestamp
            is outside the tolerance, or the signature does not match.
        PrintableError: If no secret was given or configured.
    """
    secret = _resolve_secret(secret)
    if not signature or not timestamp:
        missing = [
            header
            for header, value in ((WEBHOOK_SIGNATURE_HEADER, signature), (WEBHOOK_TIMESTAMP_HEADER, timestamp))
            if not value
        ]
        raise WebhookVerificationError(
            f"Request is missing {' and '.join(f'`{header}`' for header in missing)}. "
            "Encord signs every request it makes to a configured URL, so either this one did "
            "not come from Encord, or something between it and this endpoint dropped the header."
        )

    try:
        signed_at = int(timestamp)  # Encord signs whole seconds
    except ValueError:
        raise WebhookVerificationError(f"`{WEBHOOK_TIMESTAMP_HEADER}` is not a unix timestamp.") from None

    age_seconds = abs(time.time() - signed_at)
    if age_seconds > tolerance_seconds:
        raise WebhookVerificationError(
            f"Signed timestamp is {age_seconds:.0f}s from now, outside the {tolerance_seconds}s tolerance."
        )

    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    # Compared as bytes: `compare_digest` refuses two `str`s unless both are ASCII, and
    # the header is whatever the caller sent.
    if not hmac.compare_digest(expected.encode(), signature.encode()):
        raise WebhookVerificationError("Signature does not match the body; the secret or the payload is wrong.")


def parse_notification(body: bytes | str) -> TaskNotification:
    """Read a verified body as an agent-stage notification.

    Verify first: this trusts what it is given.

    Raises:
        UnexpectedEventType: If the body is a different Encord event.
        UnsupportedNotificationVersion: If it is that event on a later envelope version.
        pydantic.ValidationError: If it is that event but does not match the model.
    """
    envelope: dict[str, Any] = json.loads(body)

    # Checked before the version so that an event belonging to another receiver stays
    # cheap to acknowledge, whatever version it is on.
    event_type = envelope.get("event_type")
    if event_type != AGENT_STAGE_WORK_AVAILABLE_EVENT:
        raise UnexpectedEventType(str(event_type))

    version = envelope.get("version")
    if version != SUPPORTED_NOTIFICATION_VERSION:
        raise UnsupportedNotificationVersion(version)

    return TaskNotification.model_validate(envelope)


def verify_and_parse_notification(
    body: bytes,
    headers: Mapping[str, str],
    *,
    secret: str | None = None,
    tolerance_seconds: int = DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
) -> TaskNotification:
    """Verify a request and read it as an agent-stage notification.

    Raises:
        WebhookVerificationError: If the request cannot be shown to be from Encord.
        UnexpectedEventType: If it is genuine but carries a different event.
        UnsupportedNotificationVersion: If it is on a later envelope version.
        PrintableError: If no secret was given or configured.
    """
    signature = _read_header(headers, WEBHOOK_SIGNATURE_HEADER)
    if signature is None:
        unreadable = _unreadable_signature_headers(headers)
        if unreadable:
            raise WebhookVerificationError(
                f"Request carries {', '.join(f'`{header}`' for header in unreadable)} but not "
                f"`{WEBHOOK_SIGNATURE_HEADER}`, which is the signature this version of "
                "`encord-agents` reads. Upgrade the package to verify against the newer header."
            )

    verify_signature(
        body,
        secret=secret,
        signature=signature,
        timestamp=_read_header(headers, WEBHOOK_TIMESTAMP_HEADER),
        tolerance_seconds=tolerance_seconds,
    )
    return parse_notification(body)

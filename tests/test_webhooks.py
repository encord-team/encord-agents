"""Verification contract for the requests Encord signs.

The signature is computed here the way the platform computes it -- over the exact bytes
that were sent, prefixed with the timestamp -- rather than by calling the helper under
test, so these tests fail if either side of that contract moves.
"""

import hashlib
import hmac
import json
import time
from typing import Any, Callable
from uuid import UUID

import pytest

from encord_agents.core.constants import WEBHOOK_SIGNATURE_HEADER, WEBHOOK_TIMESTAMP_HEADER
from encord_agents.core.webhooks import (
    SUPPORTED_NOTIFICATION_VERSION,
    AgentStageWorkReason,
    TaskNotification,
    UnexpectedEventType,
    UnsupportedNotificationVersion,
    WebhookVerificationError,
    parse_notification,
    verify_and_parse_notification,
    verify_signature,
)
from encord_agents.exceptions import PrintableError

SECRET = "5cbf0f7d3a1e4b2c9f8a6d5e4c3b2a1908f7e6d5c4b3a2910f8e7d6c5b4a3921"
PROJECT_HASH = "11111111-1111-1111-1111-111111111111"
STAGE_UUID = "22222222-2222-2222-2222-222222222222"

ENVELOPE: dict[str, Any] = {
    "uid": "33333333-3333-3333-3333-333333333333",
    "version": 1,
    "source": "encord",
    "event_type": "agent_stage_work_available_event",
    "event_created_timestamp": "2026-09-01T12:00:00+00:00",
    "payload": {
        "project_hash": PROJECT_HASH,
        "stage_uuid": STAGE_UUID,
        "pending_count": 7,
        "reason": "batch_size_reached",
    },
}


def serialize(envelope: dict[str, Any]) -> bytes:
    """Serialize an envelope the way the platform does before signing it."""
    return json.dumps(envelope, sort_keys=True, default=str).encode()


def sign(body: bytes, *, secret: str = SECRET, timestamp: int | None = None) -> dict[str, str]:
    """Produce the headers the platform sends alongside `body`."""
    signed_at = int(time.time()) if timestamp is None else timestamp
    signature = hmac.new(secret.encode(), f"{signed_at}.".encode() + body, hashlib.sha256).hexdigest()
    return {WEBHOOK_SIGNATURE_HEADER: signature, WEBHOOK_TIMESTAMP_HEADER: str(signed_at)}


FUTURE_SIGNATURE_HEADER = f"{WEBHOOK_SIGNATURE_HEADER}-V2"
"""Stands in for a signature header added after this version of the package shipped.

The name is a placeholder: the test asserts that whatever such a header is called, it is
named back to the reader rather than swallowed.
"""


def test_accepts_a_genuine_request() -> None:
    body = serialize(ENVELOPE)
    notification = verify_and_parse_notification(body, sign(body), secret=SECRET)

    assert notification.project_hash == UUID(PROJECT_HASH)
    assert notification.stage_uuid == UUID(STAGE_UUID)
    assert notification.pending_count == 7
    assert notification.reason is AgentStageWorkReason.BATCH_SIZE_REACHED
    assert notification.uid == UUID("33333333-3333-3333-3333-333333333333")


@pytest.mark.parametrize("recase", [str.lower, str.upper])
def test_reads_headers_regardless_of_case(recase: Callable[[str], str]) -> None:
    body = serialize(ENVELOPE)
    recased = {recase(name): value for name, value in sign(body).items()}

    assert verify_and_parse_notification(body, recased, secret=SECRET).pending_count == 7


def test_rejects_a_signature_that_is_not_ascii() -> None:
    """A hostile header is a 4xx, not a crash on the way to comparing it."""
    body = serialize(ENVELOPE)
    headers = dict(sign(body), **{WEBHOOK_SIGNATURE_HEADER: "sígnature"})

    with pytest.raises(WebhookVerificationError, match="does not match"):
        verify_and_parse_notification(body, headers, secret=SECRET)


def test_rejects_a_body_changed_after_signing() -> None:
    headers = sign(serialize(ENVELOPE))
    tampered = dict(ENVELOPE, payload=dict(ENVELOPE["payload"], pending_count=9999))

    with pytest.raises(WebhookVerificationError):
        verify_and_parse_notification(serialize(tampered), headers, secret=SECRET)


def test_rejects_a_body_that_was_re_serialized() -> None:
    """The signature covers bytes, so a semantically equal re-encoding does not verify."""
    body = serialize(ENVELOPE)
    headers = sign(body)
    re_encoded = json.dumps(json.loads(body), indent=2).encode()

    with pytest.raises(WebhookVerificationError):
        verify_signature(
            re_encoded,
            secret=SECRET,
            signature=headers[WEBHOOK_SIGNATURE_HEADER],
            timestamp=headers[WEBHOOK_TIMESTAMP_HEADER],
        )


def test_rejects_another_secret() -> None:
    body = serialize(ENVELOPE)

    with pytest.raises(WebhookVerificationError):
        verify_and_parse_notification(body, sign(body), secret="a-different-secret")


@pytest.mark.parametrize("missing", [WEBHOOK_SIGNATURE_HEADER, WEBHOOK_TIMESTAMP_HEADER])
def test_rejects_a_request_without_the_headers(missing: str) -> None:
    body = serialize(ENVELOPE)
    headers = sign(body)
    del headers[missing]

    with pytest.raises(WebhookVerificationError, match=f"missing `{missing}`"):
        verify_and_parse_notification(body, headers, secret=SECRET)


def test_rejects_a_timestamp_that_is_not_a_number() -> None:
    body = serialize(ENVELOPE)

    with pytest.raises(WebhookVerificationError, match="not a unix timestamp"):
        verify_signature(body, secret=SECRET, signature="0" * 64, timestamp="yesterday")


@pytest.mark.parametrize("offset_seconds", [-3600, 3600])
def test_rejects_a_timestamp_outside_the_tolerance(offset_seconds: int) -> None:
    """Both a replayed old request and one signed in the future are refused."""
    body = serialize(ENVELOPE)
    headers = sign(body, timestamp=int(time.time()) + offset_seconds)

    with pytest.raises(WebhookVerificationError, match="outside the"):
        verify_and_parse_notification(body, headers, secret=SECRET)


def test_accepts_a_timestamp_inside_a_widened_tolerance() -> None:
    body = serialize(ENVELOPE)
    headers = sign(body, timestamp=int(time.time()) - 3600)

    assert verify_and_parse_notification(body, headers, secret=SECRET, tolerance_seconds=7200)


def test_reads_the_secret_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCORD_WEBHOOK_SECRET", SECRET)
    body = serialize(ENVELOPE)

    assert verify_and_parse_notification(body, sign(body)).pending_count == 7


def test_says_so_when_no_secret_is_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENCORD_WEBHOOK_SECRET", raising=False)
    body = serialize(ENVELOPE)

    with pytest.raises(PrintableError, match="ENCORD_WEBHOOK_SECRET"):
        verify_and_parse_notification(body, sign(body))


def test_passes_on_events_meant_for_another_receiver() -> None:
    """One URL can be configured on several stages, so other events do arrive."""
    other_event = dict(ENVELOPE, event_type="task_submitted_event")

    with pytest.raises(UnexpectedEventType) as exc_info:
        parse_notification(serialize(other_event))

    assert exc_info.value.event_type == "task_submitted_event"


def test_tolerates_fields_added_platform_side() -> None:
    """Encord adds fields without bumping the envelope version, so they must not break parsing."""
    grown = dict(
        ENVELOPE,
        delivery_attempt=2,
        payload=dict(ENVELOPE["payload"], queued_since="2026-09-01T11:00:00+00:00"),
    )

    notification = parse_notification(serialize(grown))

    assert notification.pending_count == 7
    assert notification.reason is AgentStageWorkReason.BATCH_SIZE_REACHED


def test_tolerates_a_reason_added_platform_side() -> None:
    """A new condition is additive too: keep it as its string rather than reject the notification."""
    unknown = dict(ENVELOPE, payload=dict(ENVELOPE["payload"], reason="manual_trigger"))

    notification = parse_notification(serialize(unknown))

    assert notification.reason == "manual_trigger"
    assert not isinstance(notification.reason, AgentStageWorkReason)
    assert str(notification.reason) == "manual_trigger"


def test_a_known_reason_formats_as_the_wire_value() -> None:
    """So that logging one reads the same whether or not this version knows the condition."""
    notification = parse_notification(serialize(ENVELOPE))

    assert str(notification.reason) == "batch_size_reached"
    assert f"{notification.reason}" == "batch_size_reached"


def test_refuses_an_envelope_version_it_cannot_read() -> None:
    """A version bump is reserved for a breaking change, so guessing at the payload is wrong."""
    later = dict(ENVELOPE, version=SUPPORTED_NOTIFICATION_VERSION + 1)

    with pytest.raises(UnsupportedNotificationVersion) as exc_info:
        parse_notification(serialize(later))

    assert exc_info.value.version == SUPPORTED_NOTIFICATION_VERSION + 1


def test_passes_on_another_receiver_s_event_whatever_its_version() -> None:
    """Acknowledging an event that is not ours must not depend on being able to read it."""
    other = dict(ENVELOPE, event_type="task_submitted_event", version=SUPPORTED_NOTIFICATION_VERSION + 1)

    with pytest.raises(UnexpectedEventType):
        parse_notification(serialize(other))


def test_parses_a_notification_without_verifying() -> None:
    notification = parse_notification(serialize(ENVELOPE))

    assert isinstance(notification, TaskNotification)
    assert notification.reason is AgentStageWorkReason.BATCH_SIZE_REACHED


@pytest.mark.parametrize("recase", [str.title, str.lower, str.upper])
def test_names_a_signature_header_this_version_cannot_read(recase: Callable[[str], str]) -> None:
    """Reporting a newer signature as a missing one sends the reader to the wrong fix.

    Encord may sign with a header added after this version shipped, and retire the one
    read here. Pointing at the secret would be misleading; the request is signed, just
    not in a way this version can check.
    """
    body = serialize(ENVELOPE)
    headers = sign(body)
    headers[recase(FUTURE_SIGNATURE_HEADER)] = headers.pop(WEBHOOK_SIGNATURE_HEADER)

    with pytest.raises(WebhookVerificationError) as exc_info:
        verify_and_parse_notification(body, headers, secret=SECRET)

    message = str(exc_info.value)
    assert recase(FUTURE_SIGNATURE_HEADER) in message
    assert "Upgrade the package" in message


def test_verifies_against_the_known_header_when_a_newer_one_is_also_sent() -> None:
    """Encord sends both while a signature change is rolling out; this version keeps working."""
    body = serialize(ENVELOPE)
    headers = dict(sign(body), **{FUTURE_SIGNATURE_HEADER: "a signature this version cannot verify"})

    assert verify_and_parse_notification(body, headers, secret=SECRET).pending_count == 7


def test_an_unsigned_request_still_reads_as_unsigned() -> None:
    """The newer-header message must not displace the one for a request carrying no signature."""
    body = serialize(ENVELOPE)
    headers = sign(body)
    del headers[WEBHOOK_SIGNATURE_HEADER]

    with pytest.raises(WebhookVerificationError, match=f"missing `{WEBHOOK_SIGNATURE_HEADER}`"):
        verify_and_parse_notification(body, headers, secret=SECRET)

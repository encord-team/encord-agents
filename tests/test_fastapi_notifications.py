"""Response contract for a FastAPI receiver of agent-stage notifications.

Encord reads only the status code, and records anything other than 200 as a failed
delivery, so these assert the status each outcome produces rather than the body.
Requests are signed the way the platform signs them, independently of the code under
test.
"""

import hashlib
import hmac
import json
import time
from typing import Annotated, Any
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from encord_agents.core.constants import WEBHOOK_SIGNATURE_HEADER, WEBHOOK_TIMESTAMP_HEADER
from encord_agents.core.webhooks import SUPPORTED_NOTIFICATION_VERSION, TaskNotification
from encord_agents.fastapi import add_notification_handlers, dep_task_notification, get_encord_app

SECRET = "5cbf0f7d3a1e4b2c9f8a6d5e4c3b2a1908f7e6d5c4b3a2910f8e7d6c5b4a3921"
STAGE_UUID = "22222222-2222-2222-2222-222222222222"

ENVELOPE: dict[str, Any] = {
    "uid": "33333333-3333-3333-3333-333333333333",
    "version": SUPPORTED_NOTIFICATION_VERSION,
    "source": "Encord",
    "event_type": "agent_stage_work_available_event",
    "event_created_timestamp": "2026-09-01T12:00:00+00:00",
    "payload": {
        "project_hash": "11111111-1111-1111-1111-111111111111",
        "stage_uuid": STAGE_UUID,
        "pending_count": 3,
        "reason": "batch_size_reached",
    },
}


@pytest.fixture(autouse=True)
def _configured_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCORD_WEBHOOK_SECRET", SECRET)


def serialize(envelope: dict[str, Any]) -> bytes:
    return json.dumps(envelope, sort_keys=True, default=str).encode()


def sign(body: bytes, *, secret: str = SECRET) -> dict[str, str]:
    timestamp = str(int(time.time()))
    signature = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return {WEBHOOK_SIGNATURE_HEADER: signature, WEBHOOK_TIMESTAMP_HEADER: timestamp}


def build_app(app: FastAPI) -> tuple[TestClient, list[TaskNotification]]:
    """Mount a receiver that records what reached it."""
    received: list[TaskNotification] = []

    @app.post("/encord/task-ready")
    def task_ready(notification: Annotated[TaskNotification, Depends(dep_task_notification)]) -> None:
        received.append(notification)

    return TestClient(app, raise_server_exceptions=False), received


def test_a_genuine_notification_reaches_the_route() -> None:
    client, received = build_app(get_encord_app())
    body = serialize(ENVELOPE)

    response = client.post("/encord/task-ready", content=body, headers=sign(body))

    assert response.status_code == 200, response.content
    assert [n.stage_uuid for n in received] == [UUID(STAGE_UUID)]


def test_an_unverifiable_request_is_refused_without_reaching_the_route() -> None:
    client, received = build_app(get_encord_app())
    body = serialize(ENVELOPE)

    response = client.post("/encord/task-ready", content=body, headers=sign(body, secret="another-secret"))

    assert response.status_code == 401, response.content
    assert received == []


def test_a_body_changed_after_signing_is_refused() -> None:
    client, received = build_app(get_encord_app())
    headers = sign(serialize(ENVELOPE))
    tampered = dict(ENVELOPE, payload=dict(ENVELOPE["payload"], pending_count=9999))

    response = client.post("/encord/task-ready", content=serialize(tampered), headers=headers)

    assert response.status_code == 401, response.content
    assert received == []


def test_another_receivers_event_is_acknowledged() -> None:
    """A 200 keeps it out of Encord's failed-delivery log; the route still does not run."""
    client, received = build_app(get_encord_app())
    body = serialize(dict(ENVELOPE, event_type="task_submitted_event"))

    response = client.post("/encord/task-ready", content=body, headers=sign(body))

    assert response.status_code == 200, response.content
    assert received == []


def test_an_unreadable_envelope_version_is_refused() -> None:
    client, received = build_app(get_encord_app())
    body = serialize(dict(ENVELOPE, version=SUPPORTED_NOTIFICATION_VERSION + 1))

    response = client.post("/encord/task-ready", content=body, headers=sign(body))

    assert response.status_code == 501, response.content
    assert received == []


def test_the_handlers_can_be_installed_on_an_app_built_by_hand() -> None:
    app = FastAPI()
    add_notification_handlers(app)
    client, _ = build_app(app)
    body = serialize(ENVELOPE)

    assert client.post("/encord/task-ready", content=body, headers=sign(body)).status_code == 200
    assert client.post("/encord/task-ready", content=body, headers=sign(body, secret="nope")).status_code == 401


def test_an_app_without_the_handlers_does_not_refuse_quietly() -> None:
    """Without them the failure surfaces as a 500, which is the reason they exist."""
    client, _ = build_app(FastAPI())
    body = serialize(ENVELOPE)

    assert client.post("/encord/task-ready", content=body, headers=sign(body)).status_code == 200
    assert client.post("/encord/task-ready", content=body, headers=sign(body, secret="nope")).status_code == 500

"""
Receiving the task-ready notifications an agent stage sends.

The verified notification is injected like any other dependency:

```python
from typing import Annotated
from uuid import UUID

from fastapi import BackgroundTasks, Depends

from encord_agents.core.webhooks import TaskNotification
from encord_agents.fastapi import dep_task_notification, get_encord_app

app = get_encord_app()
SERVED_PROJECTS = {UUID("<project_hash>")}

@app.post("/encord/task-ready")
def task_ready(
    notification: Annotated[TaskNotification, Depends(dep_task_notification)],
    background: BackgroundTasks,
) -> None:
    if notification.project_hash not in SERVED_PROJECTS:
        return
    background.add_task(runner.run_stage, notification.stage_uuid, project_hash=notification.project_hash)
```

Note the check. A notification says where work is waiting; it does not say what this
deployment is allowed to do, so `project_hash` is an input to check rather than an
instruction to follow. Decide which projects a deployment serves, and act only on
those.

Returning `None` answers 200, which is what Encord expects; it records any other
status as a failed delivery. Answer before doing the work, as above: Encord gives a
response 180 seconds and retries on timeout, so a handler that drains the stage inline
is re-notified while the first drain is still running.

Requests that cannot be verified never reach the route. They are turned into responses
by the handlers `get_encord_app` installs; on an app built by hand, call
[`add_notification_handlers`](#encord_agents.fastapi.notifications.add_notification_handlers)
instead, or they surface as unhandled errors.
"""

import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus

from encord_agents.core.webhooks import (
    DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
    TaskNotification,
    UnexpectedEventType,
    UnsupportedNotificationVersion,
    WebhookVerificationError,
    verify_and_parse_notification,
)

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
except ModuleNotFoundError:
    print(
        'To use the `fastapi` dependencies, you must also install fastapi. `python -m pip install "fastapi[standard]"'
    )
    exit()

logger = logging.getLogger(__name__)


async def dep_task_notification(request: Request) -> TaskNotification:
    """Verify that the request came from Encord and read it as an agent-stage notification.

    Reads the body as bytes, which is what the signature covers; a parsed and
    re-encoded body is an equivalent object with a different signature.

    Verification is authentication, not authorization: it shows the request came from
    Encord, not that `project_hash` names a project this deployment serves. Check that
    before doing any work -- see the example above.

    The signing secret comes from `ENCORD_WEBHOOK_SECRET`. To pass one explicitly, or
    to widen the timestamp tolerance, call
    [`verify_and_parse_notification`](../core/#encord_agents.core.webhooks.verify_and_parse_notification)
    from a dependency of your own.

    Raises:
        WebhookVerificationError: The request is not provably from Encord.
        UnexpectedEventType: It is, but carries an event this receiver does not read.
        UnsupportedNotificationVersion: It is on an envelope version this package cannot read.
    """
    return verify_and_parse_notification(await request.body(), request.headers)


def dep_task_notification_with_args(
    secret: str | None = None,
    tolerance_seconds: int = DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
) -> Callable[[Request], Awaitable[TaskNotification]]:
    """Build a notification dependency that does not read its secret from the environment.

    `ENCORD_WEBHOOK_SECRET` holds one secret. Use this where a single secret does not
    cover everything a deployment verifies: it gives one route the secret to verify
    against, rather than taking it from the environment.

    **Example:**

    ```python
    @app.post("/encord/task-ready")
    def task_ready(
        notification: Annotated[
            TaskNotification,
            Depends(dep_task_notification_with_args(secret=os.environ["STAGE_WEBHOOK_SECRET"])),
        ],
    ) -> None:
        ...
    ```

    Args:
        secret: The signing secret this route verifies against. Read from
            `ENCORD_WEBHOOK_SECRET` when not given.
        tolerance_seconds: How far the signed timestamp may be from now. Widen it only
            for a deployment whose clock cannot be kept closer than the default.

    Returns:
        A dependency to pass to `Depends`.
    """

    async def dependency(request: Request) -> TaskNotification:
        return verify_and_parse_notification(
            await request.body(),
            request.headers,
            secret=secret,
            tolerance_seconds=tolerance_seconds,
        )

    return dependency


async def _webhook_verification_exception_handler(request: Request, exc: WebhookVerificationError) -> JSONResponse:
    """Refuse a request that cannot be shown to have come from Encord."""
    # Logged rather than returned: the caller has not been authenticated, and which
    # check failed is of use to whoever configured the endpoint, not to them.
    logger.warning("Refused a request to `%s`: %s", request.url.path, exc)
    return JSONResponse(
        status_code=HTTPStatus.UNAUTHORIZED,
        content={"message": "Request could not be verified as coming from Encord."},
    )


async def _unexpected_event_type_exception_handler(request: Request, exc: UnexpectedEventType) -> JSONResponse:
    """Acknowledge a genuine Encord event that this receiver does not act on."""
    logger.info("Acknowledged `%s`, which this receiver does not read.", exc.event_type)
    return JSONResponse(status_code=HTTPStatus.OK, content={"message": str(exc)})


async def _unsupported_version_exception_handler(request: Request, exc: UnsupportedNotificationVersion) -> JSONResponse:
    """Refuse an envelope this version of the package cannot read."""
    logger.error("%s", exc)
    return JSONResponse(status_code=HTTPStatus.NOT_IMPLEMENTED, content={"message": str(exc)})


def add_notification_handlers(app: FastAPI) -> None:
    """Install the exception handlers that turn notification outcomes into responses.

    [`get_encord_app`](../fastapi/#encord_agents.fastapi.cors.get_encord_app) calls this
    already. Use it on an app constructed by hand, so that a request which fails
    verification is refused rather than raised as an unhandled error.

    Args:
        app: The FastAPI app serving the notification route.
    """
    app.exception_handlers[WebhookVerificationError] = _webhook_verification_exception_handler
    app.exception_handlers[UnexpectedEventType] = _unexpected_event_type_exception_handler
    app.exception_handlers[UnsupportedNotificationVersion] = _unsupported_version_exception_handler

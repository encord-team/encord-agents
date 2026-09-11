"""Drain an agent stage when Encord says there is work waiting, instead of polling.

Configure this endpoint's URL on the agent stage, read the signing secret the app
shows next to it, and set it as `ENCORD_WEBHOOK_SECRET`. Encord then calls here when
the stage's batch-size or max-wait condition is met.

Run it with:

    ENCORD_WEBHOOK_SECRET=<secret> uvicorn fastapi_task_notifications:app

The endpoint has to be reachable from the internet, so the signature is what
distinguishes Encord from anything else that finds the URL.
"""

import os
from uuid import UUID

from encord.objects.ontology_labels_impl import LabelRowV2
from fastapi import BackgroundTasks, Depends
from typing_extensions import Annotated

from encord_agents.core.webhooks import TaskNotification
from encord_agents.fastapi.cors import get_encord_app
from encord_agents.fastapi.notifications import dep_task_notification
from encord_agents.tasks import Runner

PROJECT_HASH = UUID(os.environ["ENCORD_PROJECT_HASH"])

app = get_encord_app()
runner = Runner(project_hash=str(PROJECT_HASH))


@runner.stage("<stage_name_or_uuid>")
def my_agent(lr: LabelRowV2) -> str:
    """Whatever the stage should do to a task. Returns the pathway to move it along."""
    return "<pathway_name>"


@app.post("/encord/task-ready")
def task_ready(
    notification: Annotated[TaskNotification, Depends(dep_task_notification)],
    background: BackgroundTasks,
) -> None:
    """Acknowledge the notification, then drain the stage out of band.

    Verification shows the request came from Encord. It does not show the request
    concerns a project this deployment serves: the signing secret belongs to the URL
    rather than to a project. So the project is checked here, and `run_stage` is left
    to use the runner's own -- a notification never decides which project this
    service acts on, only when to look.
    """
    if notification.project_hash != PROJECT_HASH:
        return

    # Answering first is not politeness: Encord gives the response 180 seconds and
    # retries on timeout, and re-notifies every few minutes while work remains, so a
    # drain running inline would be started again underneath itself.
    background.add_task(runner.run_stage, notification.stage_uuid)

from typing import Annotated
from uuid import UUID

from celery import Celery
from encord.objects.ontology_labels_impl import LabelRowV2

from encord_agents.tasks import QueueRunner

# Initialize Celery app
celery_app = Celery(
    "encord_agent_tasks",
    broker="amqp://guest:guest@localhost:5672//",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_backend="sqlite:///results.db",
    database_engine_options={"echo": True},
    worker_concurrency=4,  # Use 4 workers
)

# Initialize the QueueRunner with your project
runner = QueueRunner(project_hash="<your-project-hash>")


# Define your agent implementation
@runner.stage("<agent-stage-name>")
def agent_stage_name(
    lr: LabelRowV2,
) -> str | UUID | None:
    """
    Example agent that processes video frames.
    Replace with your actual processing logic.
    """
    # Implement your agent logic here

    return "<next-stage-name>"  # or UUID of the next stage


# Create a Celery task to execute the wrapped agent
@celery_app.task(name="celery_function_name")
def celery_function(task_spec: str) -> str:
    """
    Celery task that executes the agent on a specific task.

    Args:
        task_spec: JSON string containing the task specification

    Returns:
        JSON string containing the task completion result
    """
    return agent_stage_name(task_spec)

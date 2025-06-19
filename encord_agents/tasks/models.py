from dataclasses import dataclass
from typing import Callable, TypeVar
from uuid import UUID

from encord.objects.ontology_labels_impl import LabelRowV2
from pydantic import BaseModel, Field

TaskAgentReturnPathway = str | UUID | None


@dataclass
class TaskAgentReturnStruct:
    """
    Return this from your agent and we handle propagating the updates in batches
    """

    pathway: TaskAgentReturnPathway = None
    """
    The pathway that the task follows upon task completion
    """
    label_row: LabelRowV2 | None = None
    """
    The label to be saved (if present)
    """
    label_row_priority: float | None = None
    """
    The priority of the label row to be saved.
    """


TaskAgentReturnType = TaskAgentReturnPathway | TaskAgentReturnStruct

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., TaskAgentReturnType])


class AgentTaskConfig(BaseModel):
    task_uuid: UUID = Field(description="The task uuid", validation_alias="uuid")
    data_hash: UUID = Field(description="The data hash of the underlying asset")
    data_title: str = Field(description="The data title used in the Encord system")
    label_branch_name: str = Field(description="The branch name of the associated labels")


class TaskCompletionResult(BaseModel):
    """
    Data model to hold information about the completion result of
    `encord_agents.tasks.QueueRunner` agents.
    """

    task_uuid: UUID = Field(description="UUID of the task in the Encord Queueing system")
    stage_uuid: UUID | None = Field(
        description="UUID of the workflow stage at which the task was executed. If None, the stage could not be identified from the `task_uuid`.",
        default=None,
    )
    success: bool = Field(description="Agent executed without errors")
    pathway: UUID | None = Field(
        description="The UUID of the pathway that the task was passed along to. If None, either the agent succeeded but didn't return a pathway or the agent failed so the task didn't proceed.",
        default=None,
    )
    error: str | None = Field(description="Stack trace or error message if an error occurred", default=None)

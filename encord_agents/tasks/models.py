from uuid import UUID

from encord.workflow.stages.agent import AgentTask
from pydantic import BaseModel, Field


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
    # TODO: When we can read pathway definitions via the `encord` SDK, pathway can be typed None | UUID only.
    # Currently, pathway can also be the name of the pathway.
    pathway: str | UUID | None = Field(
        description="The pathway that the task was passed along to. If None, either the agent succeded but didn't return a pathway or the agent failed so the task didn't proceed.",
        default=None,
    )
    error: str | None = Field(description="Stack trace or error message if an error occured", default=None)

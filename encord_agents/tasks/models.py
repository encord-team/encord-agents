from uuid import UUID

from pydantic import BaseModel, Field


class AgentTaskConfig(BaseModel):
    uuid: UUID = Field(description="The task uuid")
    data_hash: UUID = Field(description="The data hash of the underlying asset")
    data_title: str = Field(description="The data title used in the Encord system")
    label_branch_name: str = Field(description="The branch name of the associated labels")


class TaskCompletionResult(BaseModel):
    success: bool = Field(description="Agent executed without errors")
    next_stage: str | UUID | None = Field(description="The pathway that the task was passed along to", default=None)
    error: str | None = Field(description="Stack trace or error message if an error occured", default=None)

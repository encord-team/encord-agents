from uuid import UUID

from pydantic import BaseModel, Field


class FrameData(BaseModel):
    project_hash: UUID = Field(validation_alias="projectHash")
    data_hash: UUID = Field(validation_alias="dataHash")
    frame: int = Field(ge=0)

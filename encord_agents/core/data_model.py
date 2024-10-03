from uuid import UUID

from pydantic import BaseModel, Field


class FrameData(BaseModel):
    project_hash: UUID
    data_hash: UUID
    frame_number: int = Field(ge=0)

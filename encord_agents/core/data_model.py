from dataclasses import dataclass
from uuid import UUID

import numpy as np
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class VideoFrame:
    frame: int
    content: np.ndarray
    """
    The content will be [h,w,c] np.arrays in RGB format.
    """


class FrameData(BaseModel):
    project_hash: UUID = Field(validation_alias="projectHash")
    data_hash: UUID = Field(validation_alias="dataHash")
    frame: int = Field(ge=0)

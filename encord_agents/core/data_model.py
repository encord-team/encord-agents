from dataclasses import dataclass
from uuid import UUID

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, Field


class FrameData(BaseModel):
    """
    Holds the data sent from the Encord Label Editor at the time of triggering the agent.
    """

    project_hash: UUID = Field(validation_alias="projectHash")
    """
    The identifier of the given project.
    """
    data_hash: UUID = Field(validation_alias="dataHash")
    """
    The identifier of the given data asset.
    """
    frame: int = Field(ge=0)
    """
    The frame number. If single image, it's default 0.
    """


@dataclass(frozen=True)
class Frame:
    """
    A dataclass to hold the content of one frame in a video.
    """

    frame: int
    """
    The frame number within the video
    """
    content: "NDArray[np.uint8]"
    """
    An [h,w,c] np.array with color channels RGB.
    """

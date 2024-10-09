from typing import Annotated

import cv2
import numpy as np
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.user_client import EncordUserClient
from fastapi import Depends

from encord_agents.core.data_model import FrameData
from encord_agents.core.utils import (
    download_asset,
    get_initialised_label_row,
    get_user_client,
)
from encord_agents.core.video import iter_video


def dep_client() -> EncordUserClient:
    """
    Dependency to provide an authenticated user client.
    """
    return get_user_client()


def dep_label_row(frame_data: FrameData) -> LabelRowV2:
    """
    Match a unique label row in a project based on data_hash.
    Additionally, initialise the label row to download the label data.
    :param frame_data: the data that defines what the user triggering the agent is looking at.
    :return: An initialised label row matched on data_hash.
    """
    return get_initialised_label_row(frame_data)


def dep_asset(lr: Annotated[LabelRowV2, Depends(dep_label_row)], frame_data: FrameData):
    """
    Download the underlying asset being annotated (video, image) in a specific label row to disk.
    The downloaded asset will be named `lr.data_hash.{suffix}`.
    When the context is exited, the downloaded file will be removed.
    :param lr: The label row for whose asset should be downloaded.
    :param frame_data: The data that defines what the user triggering the agent is looking at.
    :return: The np.ndarray of shape [h, w, 3] RGB colors.
    """
    # TODO test if this will work for reading it from within the fastapi function
    with download_asset(lr, frame_data.frame) as asset:
        img = cv2.cvtColor(cv2.imread(asset.as_posix()), cv2.COLOR_BGR2RGB)
    return np.asarray(img, dtype=np.uint8)


def dep_video_iterator(lr: Annotated[LabelRowV2, Depends(dep_label_row)]):
    with download_asset(lr, None) as asset:
        yield iter_video(asset)

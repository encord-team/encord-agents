"""
Dependencies for injection in FastAPI servers.

This module contains dependencies that you can inject within your api routes.
Dependencies that depend on others don't need to be used together. They'll
work just fine alone.
"""

from typing import Annotated, Generator, Iterator

import cv2
import numpy as np
from encord.constants.enums import DataType
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.user_client import EncordUserClient

try:
    from fastapi import Depends
except ModuleNotFoundError:
    print(
        'To use the `fastapi` dependencies, you must also install fastapi. `python -m pip install "fastapi[standard]"'
    )
    exit()

from encord_agents.core.data_model import Frame, FrameData
from encord_agents.core.utils import (
    download_asset,
    get_initialised_label_row,
    get_user_client,
)
from encord_agents.core.video import iter_video


def dep_client() -> EncordUserClient:
    """
    Dependency to provide an authenticated user client.

    Intended use:

        from encord.user_client import EncordUserClient
        from encord_agents.fastapi.depencencies import dep_client
        ...
        @app.post("/my-route")
        def my_route(
            client: Annotated[EncordUserClient, Depends(dep_client)]
        ):
            # Client will authenticated and ready to use.

    """
    return get_user_client()


def dep_label_row(frame_data: FrameData) -> LabelRowV2:
    """
    Dependency to provide an initialized label row.

    Intended use:

        from encord_agents import FrameData
        from encord_agents.fastapi.depencencies import dep_label_row
        ...

        @app.post("/my-route")
        def my_route(
            frame_data: FrameData,  # <- Automatically injected
            lr: Annotated[LabelRowV2, Depends(dep_label_row)]
        ):
            assert lr.is_labelling_initialised  # will work

    Args:
        frame_data: the frame data from the route. This parameter is automatically injected
            if it's a part of your route (see example above)

    Returns:
        The initialized label row.

    """
    return get_initialised_label_row(frame_data)


def dep_single_frame(lr: Annotated[LabelRowV2, Depends(dep_label_row)], frame_data: FrameData):
    """
    Dependency to inject the underlying asset of the frame data.

    The downloaded asset will be named `lr.data_hash.{suffix}`.
    When the function has finished, the downloaded file will be removed from the file system.

    Intended use:

        from encord_agents import FrameData
        from encord_agents.fastapi.depencencies import dep_single_frame
        ...

        @app.post("/my-route")
        def my_route(
            frame_data: FrameData,  # <- Automatically injected
            frame: Annotated[NDArray[np.uint8], Depends(dep_single_frame)]
        ):
            assert arr.ndim == 3, "Will work"

    Args:
        lr: The label row. Automatically injected (see example above).
        frame_data: the frame data from the route. This parameter is automatically injected
            if it's a part of your route (see example above).

    Returns: Numpy array of shape [h, w, 3] RGB colors.

    """
    with download_asset(lr, frame_data.frame) as asset:
        img = cv2.cvtColor(cv2.imread(asset.as_posix()), cv2.COLOR_BGR2RGB)
    return np.asarray(img, dtype=np.uint8)


def dep_video_iterator(lr: Annotated[LabelRowV2, Depends(dep_label_row)]) -> Generator[Iterator[Frame], None, None]:
    """
    Dependency to inject a video frame iterator for doing things over many frames.

    Intended use:

        from encord_agents import FrameData
        from encord_agents.fastapi.depencencies import dep_video_iterator
        ...

        @app.post("/my-route")
        def my_route(
            frame_data: FrameData,  # <- Automatically injected
            video_frames: Annotated[Iterator[Frame], Depends(dep_video_iterator)]
        ):
            for frame in video_frames:
                print(frame.frame, frame.content.shape)

    Args:
        lr: Automatically injected label row dependency.

    Raises:
        NotImplementedError: Will fail for other data types than video.

    Yields:
        An iterator.

    """
    if not lr.data_type == DataType.VIDEO:
        raise NotImplementedError("`dep_video_iterator` only supported for video label rows")
    # TODO test if this will work in api server
    with download_asset(lr, None) as asset:
        yield iter_video(asset)

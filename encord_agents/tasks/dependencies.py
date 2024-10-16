from pathlib import Path
from typing import Generator, Iterator

import cv2
import numpy as np
from encord.constants.enums import DataType
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.user_client import EncordUserClient
from numpy.typing import NDArray

from encord_agents.core.data_model import Frame
from encord_agents.core.utils import download_asset, get_user_client
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


def dep_single_frame(lr: LabelRowV2) -> NDArray[np.uint8]:
    """
    Dependency to inject the first frame of the underlying asset.

    The downloaded asset will be named `lr.data_hash.{suffix}`.
    When the function has finished, the downloaded file will be removed from the file system.

    Intended use:

        from encord_agents import FrameData
        from encord_agents.fastapi.depencencies import dep_asset
        ...

        @runner.stage("<my_stage_name>")
        def my_agent(
            lr: LabelRowV2,  # <- Automatically injected
            frame: Annotated[NDArray[np.uint8], Depends(dep_single_frame)] 
        ):
            assert frame.ndim == 3, "Will work"

    Args:
        lr: The label row. Automatically injected (see example above).

    Returns: 
        Numpy array of shape [h, w, 3] RGB colors.

    """
    with download_asset(lr, frame=0) as asset:
        img = cv2.cvtColor(cv2.imread(asset.as_posix()), cv2.COLOR_BGR2RGB)

    return np.asarray(img, dtype=np.uint8)



def dep_video_iterator(lr: LabelRowV2) -> Generator[Iterator[Frame], None, None]:
    """
    Dependency to inject a video frame iterator for doing things over many frames.

    Intended use:

        from encord_agents import FrameData
        from encord_agents.fastapi.depencencies import dep_video_iterator
        ...

        @runner.stage("<stage-name>")
        def my_agent(
            lr: LabelRowV2,  # <- Automatically injected
            video_frames: Annotated[Iterator[VideoFrame], Depends(dep_video_iterator)]
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

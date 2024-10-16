from pathlib import Path
from typing import Iterator

import cv2
import numpy as np
from numpy.typing import NDArray

from encord_agents.core.data_model import Frame


def get_frame(video_path: Path, desired_frame: int) -> NDArray[np.uint8]:
    """
    Extract an exact frame from a video.

    Args:
        video_path: The file path to where the video is stored.
        desired_frame: The frame to extract

    Raises:
        Exception:  If the video cannot be opened properly or the requested
            frame could not be retrieved from the video.

    Returns:
        Numpy array of shape [h, w, c] where channels are RGB.

    """
    cap = cv2.VideoCapture(video_path.as_posix())
    if not cap.isOpened():
        raise Exception("Error opening video file.")

    cap.set(cv2.CAP_PROP_POS_FRAMES, desired_frame)

    ret, frame = cap.read()
    if not ret:
        raise Exception("Error retrieving frame.")

    cap.release()
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return frame.astype(np.uint8)


def iter_video(video_path: Path) -> Iterator[Frame]:
    """
    Iterate video frame by frame.

    Args:
        video_path: The file path to the video you wish to iterate.

    Raises:
        Exception: If the video file could not be opened properly.

    Yields:
        Frames from the video.

    """
    cap = cv2.VideoCapture(video_path.as_posix())
    if not cap.isOpened():
        raise Exception("Error opening video file.")

    frame_num = 0
    ret, frame = cap.read()
    while ret:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        yield Frame(frame=frame_num, content=rgb_frame.astype(np.uint8))

        ret, frame = cap.read()
        frame_num += 1

    cap.release()

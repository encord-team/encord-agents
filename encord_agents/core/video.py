from pathlib import Path
from typing import Iterable, Iterator

import numpy as np
from numpy.typing import NDArray

try:
    import cv2
except ImportError:
    raise ImportError(
        "Your data agent is depending on computer vision capabilities and `opencv` is not installed. Please install either `opencv-python` or `opencv-python-headless`."
    )


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
        Numpy array of shape [h, w, c] where channels are BGR.

    """
    cap = cv2.VideoCapture(video_path.as_posix())
    if not cap.isOpened():
        raise Exception("Error opening video file.")

    cap.set(cv2.CAP_PROP_POS_FRAMES, desired_frame)

    ret, frame = cap.read()
    if not ret:
        raise Exception("Error retrieving frame.")

    cap.release()
    return frame.astype(np.uint8)


def write_frame(frame_path: Path, frame: NDArray[np.uint8]) -> None:
    """
    Write a frame to a file.

    Args:
        frame_path: The file path to write the frame to.
        frame: The frame to write.

    """
    cv2.imwrite(frame_path.as_posix(), frame)


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


def iter_video_with_indices(video_path: Path, frame_indices: Iterable[int]) -> Iterator[Frame]:
    """
    Iterate video frame by frame with specified frame indices.

    Args:
        video_path: The file path to the video you wish to iterate.
        frame_indices: The frame indices to iterate over.

    Yields:
        Frames from the video.

    """
    if not video_path.exists():
        raise Exception("Video file does not exist.")
    cap = cv2.VideoCapture(video_path.as_posix())
    if not cap.isOpened():
        raise Exception("Error opening video file.")

    for frame_num in frame_indices:
        # Set the frame position before reading
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        if not ret:
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        yield Frame(frame=frame_num, content=rgb_frame.astype(np.uint8))

    cap.release()

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

from .data_model import VideoFrame


def get_frame(video_path: Path, desired_frame: int) -> np.ndarray:
    """
    Extract a given frame from a downloaded video.
    :param video_path: The path to which the video was downloaded.
    :param desired_frame: The frame which you would like to extract.
    :return: The extracted frame.
    """
    cap = cv2.VideoCapture(video_path.as_posix())
    if not cap.isOpened():
        raise Exception("Error opening video file.")

    cap.set(cv2.CAP_PROP_POS_FRAMES, desired_frame)

    ret, frame = cap.read()
    if not ret:
        raise Exception("Error retrieving frame.")

    cap.release()
    return frame


@dataclass(frozen=True)
class VideoFrame:
    frame: int
    content: np.ndarray
    """
    The content will be [h,w,c] np.arrays in RGB format.
    """


def iter_video(video_path: Path) -> Iterator[VideoFrame]:
    cap = cv2.VideoCapture(video_path.as_posix())
    if not cap.isOpened():
        raise Exception("Error opening video file.")

    frame_num = 0
    ret, frame = cap.read()
    while ret:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        yield VideoFrame(frame=frame_num, content=rgb_frame)

        ret, frame = cap.read()
        frame_num += 1

    cap.release()
    return frame

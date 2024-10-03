import mimetypes
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Generator

import cv2
import numpy as np
import requests
from encord.constants.enums import DataType
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.user_client import EncordUserClient

from encord_agents.core.data_model import FrameData
from encord_agents.core.settings import Settings


@lru_cache(maxsize=1)
def get_user_client() -> EncordUserClient:
    """
    Generate an user client to access Encord.
    :param settings: system settings to tell where ssh key file is stored.
    :return: An EncordUserClient using the right credentials and connection string.
    """
    settings = Settings()
    return EncordUserClient.create_with_ssh_private_key(
        ssh_private_key_path=settings.ssh_key_file,
    )


def get_initialised_label_row(frame_data: FrameData) -> LabelRowV2:
    """
    Match a unique label row in a project based on data_hash.
    Additionally, initialise the label row to download the label data.
    :param frame_data: FrameData object containing the project_hash and data_hash to match against.
    :return: An initialised label row matched on data_hash.
    """
    user_client = get_user_client()
    project = user_client.get_project(frame_data.project_hash)
    matched_lrs = project.list_label_rows_v2(data_hashes=[frame_data.data_hash])
    num_matches = len(matched_lrs)
    if num_matches > 1:
        raise Exception(f"Non unique match: matched {num_matches} label rows!")
    elif num_matches == 0:
        raise Exception("No label rows were matched!")
    lr = matched_lrs.pop()
    lr.initialise_labels(include_signed_url=True)
    return lr


def _guess_file_suffix(url: str, lr: LabelRowV2) -> str:
    """
    Best effort attempt to guess file suffix based on information in following order:

        0. `url`
        1. `lr.data_title`
        2. `lr.data_type` (fallback)

    args:
        - url: the data url
        - lr: the associated label row

    returns:
        a file suffix that can be used to store the file. For example, ".jpg" or ".mp4"

    """
    fallback_mimetype = "video/mp4" if lr.data_type == DataType.VIDEO else "image/png"
    mimetype, _ = next(
        (
            t
            for t in (
                mimetypes.guess_type(url),
                mimetypes.guess_type(lr.data_title),
                (fallback_mimetype, None),
            )
            if t[0] is not None
        )
    )
    if mimetype is None:
        raise ValueError("This should not have happened")

    file_type, suffix = mimetype.split("/")[:2]

    if file_type == "video" and lr.data_type != DataType.VIDEO:
        raise ValueError(
            f"Mimetype {mimetype} and lr data type {lr.data_type} did not match"
        )
    elif file_type == "image" and lr.data_type not in {
        DataType.IMG_GROUP,
        DataType.IMAGE,
    }:
        raise ValueError(
            f"Mimetype {mimetype} and lr data type {lr.data_type} did not match"
        )
    elif file_type not in {"image", "video"}:
        raise ValueError("File type not video or image")

    return f".{suffix}"


@contextmanager
def download_asset(
    lr: LabelRowV2, frame_number: int | None
) -> Generator[Path, None, None]:
    """
    Download the underlying asset being annotated (video, image) in a specific label row to disk.
    The downloaded asset will be named `lr.data_hash.{suffix}`.
    When the context is exited, the downloaded file will be removed.
    :param lr: The label row for whose asset should be downloaded.
    :param frame_number The frame to extract of the entire thing as is if None
    :return: The path to which the asset was downloaded.
    """
    video_item, images_list = lr._project_client.get_data(
        lr.data_hash, get_signed_url=True
    )
    if lr.data_type in [DataType.VIDEO, DataType.IMAGE] and video_item:
        url = video_item["file_link"]
    elif lr.data_type == DataType.IMG_GROUP and images_list:
        if frame_number is None:
            raise NotImplementedError("Downloading entire image group is not supported")
        url = images_list[frame_number]["file_link"]
    else:
        raise ValueError("Couldn't load asset")

    response = requests.get(url)
    response.raise_for_status()

    suffix = _guess_file_suffix(url, lr)
    file_path = Path(lr.data_hash).with_suffix(suffix)
    with open(file_path, "wb") as f:
        f.write(response.content)

    files_to_unlink = [file_path]
    if (
        lr.data_type == DataType.VIDEO and frame_number is not None
    ):  # Get that exact frame
        frame = get_frame(file_path, frame_number)
        frame_file = file_path.with_name(
            f"{file_path.name}_{frame_number}"
        ).with_suffix(".png")
        cv2.imwrite(frame_file.as_posix(), frame)
        files_to_unlink.append(frame_file)
        file_path = frame_file
    try:
        yield file_path
    finally:
        [f.unlink(missing_ok=True) for f in files_to_unlink]


# def extract_frames_from_video(
#     video_file_path: Path,
#     data_hash: str,
#     max_secs: int | None = None,
#     start_at_frame: int = 0,
# ) -> tuple[list[Path], list[str]]:
#     logging.info(
#         f"Extracting {video_file_path} at one frame per second. This might take a bit..."
#     )
#     frames_dir = Path(data_hash)
#     frames_dir.mkdir(exist_ok=True)
#
#     vidcap = cv2.VideoCapture(video_file_path.as_posix())
#     vidcap.set(cv2.CAP_PROP_POS_FRAMES, start_at_frame)
#
#     fps = vidcap.get(cv2.CAP_PROP_FPS)
#     output_file_prefix = video_file_path.stem.replace(".", "_")
#     frame_count = 0
#     count = 0
#     paths = []
#     time_strings = []
#
#     while vidcap.isOpened():
#         success, frame = vidcap.read()
#         if not success or (max_secs and len(paths) >= max_secs):  # End of video
#             break
#         if (count // fps) == frame_count:  # Extract a frame every second
#             min = frame_count // 60
#             sec = frame_count % 60
#             time_string = f"{min:02d}:{sec:02d}"
#             image_name = f"{output_file_prefix}_frame{time_string}.jpg"
#             output_file = frames_dir / image_name
#             cv2.imwrite(output_file.as_posix(), frame)
#             frame_count += 1
#             time_strings.append(time_string)
#             paths.append(output_file)
#         count += 1
#     vidcap.release()  # Release the capture object\n",
#     return paths, time_strings
#
#

# @contextmanager
# def get_video_frames_and_time_stamps(
#     lr: LabelRowV2, start: int, extend: int = 50
# ) -> Generator[tuple[list[Path], list[str]], None, None]:
#     with download_asset(lr, frame_number=None) as video_path:
#         frame_paths, time_stamps = extract_frames_from_video(
#             video_path, lr.data_hash, max_secs=extend, start_at_frame=start
#         )
#     try:
#         yield (frame_paths, time_stamps)
#     finally:
#         shutil.rmtree(frame_paths[0].parent)
#


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

import mimetypes
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Generator

import cv2
import requests
from encord.constants.enums import DataType
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.user_client import EncordUserClient

from encord_agents.core.data_model import FrameData
from encord_agents.core.settings import Settings

from .video import get_frame


@lru_cache(maxsize=1)
def get_user_client() -> EncordUserClient:
    """
    Generate an user client to access Encord.

    Returns:
        An EncordUserClient authenticated with the credentials from the encord_agents.core.settings.Settings.

    """
    settings = Settings()  # type: ignore
    return EncordUserClient.create_with_ssh_private_key(
        ssh_private_key=settings.ssh_key,
    )


def get_initialised_label_row(frame_data: FrameData) -> LabelRowV2:
    """
    Get an initialised label row from the frame_data information.

    Args:
        frame_data: The data pointing to the data asset.

    Raises:
        Exception: If the `frame_data` cannot be matched to a label row

    Returns:
        The initialized label row.

    """
    user_client = get_user_client()
    project = user_client.get_project(str(frame_data.project_hash))
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
    Best effort attempt to guess file suffix given a url and label row.

    Guesses are based on information in following order:

        0. `url`
        1. `lr.data_title`
        2. `lr.data_type` (fallback)

    Args:
        - url: the data url from which the asset is downloaded.
        - lr: the associated label row

    Returns:
        A file suffix that can be used to store the file. For example, ".jpg" or ".mp4"

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
        raise ValueError(f"Mimetype {mimetype} and lr data type {lr.data_type} did not match")
    elif file_type == "image" and lr.data_type not in {
        DataType.IMG_GROUP,
        DataType.IMAGE,
    }:
        raise ValueError(f"Mimetype {mimetype} and lr data type {lr.data_type} did not match")
    elif file_type not in {"image", "video"}:
        raise ValueError("File type not video or image")

    return f".{suffix}"


@contextmanager
def download_asset(lr: LabelRowV2, frame: int | None) -> Generator[Path, None, None]:
    """
    Download the asset associated to a label row to disk.

    This function is a context manager. Data will be cleaned up when the context is left.

    Example usage:

        with download_asset(lr, 10) as asset_path:
            # In here the file exists
            pixel_values = np.asarray(Image.open(asset_path))

        # outside, it will be cleaned up

    Args:
        lr: The label row for which you want to download the associated asset.
        frame: The frame that you need. If frame is none for a video, you will get the video path.

    Raises:
        NotImplementedError: If you try to get all frames of an image group.
        ValueError: If you try to download an unsupported data type (e.g., DICOM).


    Yields:
        The file path for the requested asset.

    """
    video_item, images_list = lr._project_client.get_data(lr.data_hash, get_signed_url=True)
    if lr.data_type in [DataType.VIDEO, DataType.IMAGE] and video_item:
        url = video_item["file_link"]
    elif lr.data_type == DataType.IMG_GROUP and images_list:
        if frame is None:
            raise NotImplementedError(
                "Downloading entire image group is not supported. Please contact Encord at support@encord.com for help or submit a PR with an implementation."
            )
        url = images_list[frame]["file_link"]
    else:
        raise ValueError(f"Couldn't load asset of type {lr.data_type}")

    response = requests.get(url)
    response.raise_for_status()

    suffix = _guess_file_suffix(url, lr)
    file_path = Path(lr.data_hash).with_suffix(suffix)
    with open(file_path, "wb") as f:
        f.write(response.content)

    files_to_unlink = [file_path]
    if lr.data_type == DataType.VIDEO and frame is not None:  # Get that exact frame
        frame_content = get_frame(file_path, frame)
        frame_file = file_path.with_name(f"{file_path.name}_{frame}").with_suffix(".png")
        cv2.imwrite(frame_file.as_posix(), frame_content)
        files_to_unlink.append(frame_file)
        file_path = frame_file
    try:
        yield file_path
    finally:
        [f.unlink(missing_ok=True) for f in files_to_unlink]

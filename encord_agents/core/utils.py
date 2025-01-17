import mimetypes
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Generator, cast

import cv2
import requests
from encord.constants.enums import DataType
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.user_client import EncordUserClient

from encord_agents import __version__
from encord_agents.core.data_model import FrameData, LabelRowInitialiseLabelsArgs, LabelRowMetadataIncludeArgs
from encord_agents.core.settings import Settings

from .video import get_frame


@lru_cache(maxsize=1)
def get_user_client() -> EncordUserClient:
    """
    Generate an user client to access Encord.

    Returns:
        An EncordUserClient authenticated with the credentials from the encord_agents.core.settings.Settings.

    """
    settings = Settings()
    kwargs: dict[str, Any] = {"user_agent_suffix": f"encord-agents/{__version__}"}

    if settings.domain:
        kwargs["domain"] = settings.domain
    return EncordUserClient.create_with_ssh_private_key(ssh_private_key=settings.ssh_key, **kwargs)


def get_initialised_label_row(
    frame_data: FrameData,
    include_args: LabelRowMetadataIncludeArgs | None = None,
    init_args: LabelRowInitialiseLabelsArgs | None = None,
) -> LabelRowV2:
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
    include_args = include_args or LabelRowMetadataIncludeArgs()
    init_args = init_args or LabelRowInitialiseLabelsArgs()
    matched_lrs = project.list_label_rows_v2(data_hashes=[frame_data.data_hash], **include_args.model_dump())
    num_matches = len(matched_lrs)
    if num_matches > 1:
        raise Exception(f"Non unique match: matched {num_matches} label rows!")
    elif num_matches == 0:
        raise Exception("No label rows were matched!")
    lr = matched_lrs.pop()
    lr.initialise_labels(**init_args.model_dump())
    return lr


def _guess_file_suffix(url: str, lr: LabelRowV2) -> tuple[str, str]:
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
        A file type and suffix that can be used to store the file.
        For example, ("image", ".jpg") or ("video", ".mp4").
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

    if (file_type == "audio" and lr.data_type != DataType.AUDIO) or (
        file_type == "video" and lr.data_type != DataType.VIDEO
    ):
        raise ValueError(f"Mimetype {mimetype} and lr data type {lr.data_type} did not match")
    elif file_type == "image" and lr.data_type not in {
        DataType.IMG_GROUP,
        DataType.IMAGE,
    }:
        raise ValueError(f"Mimetype {mimetype} and lr data type {lr.data_type} did not match")
    elif file_type not in {"image", "video", "audio"}:
        raise ValueError("File type not audio, video, or image")

    return file_type, f".{suffix}"


@contextmanager
def download_asset(lr: LabelRowV2, frame: int | None = None) -> Generator[Path, None, None]:
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
    url: str | None = None
    if lr.data_link is not None and lr.data_link[:5] == "https":
        url = lr.data_link
    elif lr.backing_item_uuid is not None:
        storage_item = get_user_client().get_storage_item(lr.backing_item_uuid, sign_url=True)
        url = storage_item.get_signed_url()

    # Fallback for native image groups (they don't have a url)
    is_image_sequence = lr.data_type == DataType.IMG_GROUP
    if url is None:
        is_image_sequence = False
        _, images_list = lr._project_client.get_data(lr.data_hash, get_signed_url=True)
        if images_list is None:
            raise ValueError("Image list should not be none for image groups.")
        if frame is None:
            raise NotImplementedError(
                "Downloading entire image group is not supported. Please contact Encord at support@encord.com for help or submit a PR with an implementation."
            )
        image = images_list[frame]
        url = cast(str | None, image.file_link)

    if url is None:
        raise ValueError("Failed to get a signed url for the asset")

    response = requests.get(url)
    response.raise_for_status()

    with TemporaryDirectory() as dir_name:
        dir_path = Path(dir_name)

        _, suffix = _guess_file_suffix(url, lr)
        file_path = dir_path / f"{lr.data_hash}{suffix}"
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:
                    f.write(chunk)

        if (lr.data_type == DataType.VIDEO or is_image_sequence) and frame is not None:  # Get that exact frame
            frame_content = get_frame(file_path, frame)
            frame_file = file_path.with_name(f"{file_path.name}_{frame}").with_suffix(".png")
            cv2.imwrite(frame_file.as_posix(), frame_content)
            file_path = frame_file

        yield file_path

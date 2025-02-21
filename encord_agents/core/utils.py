import mimetypes
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Generator, Iterable, List, TypeVar, cast

import cv2
import requests
from encord.constants.enums import DataType
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.orm.storage import StorageItemType
from encord.storage import StorageItem
from encord.user_client import EncordUserClient

from encord_agents import __version__
from encord_agents.core.data_model import FrameData, LabelRowInitialiseLabelsArgs, LabelRowMetadataIncludeArgs
from encord_agents.core.settings import Settings

from .video import get_frame

DOWNLOAD_NATIVE_IMAGE_GROUP_WO_FRAME_ERROR_MESSAGE = (
    "`frame` parameter set to None for a Native Image Group. "
    "Downloading entire native image group is currently not supported. "
    "Please contact Encord at support@encord.com for help or submit a PR with an implementation."
)


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


def translate_suffixes_to_filesystem_suffixes(suffix: str) -> str:
    return suffix.replace("plain", "txt").replace("mpeg", "mp3")


_FALLBACK_MIMETYPES: dict[StorageItemType | DataType, str] = {
    DataType.VIDEO: "video/mp4",
    DataType.IMAGE: "video/jpeg",
    DataType.AUDIO: "audio/mp3",
    DataType.PDF: "application/pdf",
    DataType.PLAIN_TEXT: "text/plain",
    StorageItemType.VIDEO: "video/mp4",
    StorageItemType.AUDIO: "audio/mp3",
    StorageItemType.IMAGE_SEQUENCE: "video/mp4",
    StorageItemType.IMAGE: "image/png",
    StorageItemType.PDF: "application/pdf",
    StorageItemType.PLAIN_TEXT: "text/plain",
}


def _guess_file_suffix(url: str, lr: LabelRowV2, storage_item: StorageItem | None = None) -> tuple[str, str]:
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
    fallback_mimetype = _FALLBACK_MIMETYPES.get(
        storage_item.item_type if storage_item is not None else lr.data_type, None
    )
    if fallback_mimetype is None:
        raise ValueError(f"No fallback mimetype found for data type {lr.data_type}")

    mimetype = next(
        (
            t
            for t in (
                storage_item.mime_type if storage_item is not None else None,
                mimetypes.guess_type(url)[0],
                mimetypes.guess_type(storage_item.name)[0] if storage_item is not None else None,
                mimetypes.guess_type(lr.data_title)[0],
                fallback_mimetype,
            )
            if t is not None
        )
    )
    if mimetype is None:
        raise ValueError("This should not have happened")

    file_type, suffix = mimetype.split("/")[:2]

    suffix = translate_suffixes_to_filesystem_suffixes(suffix)
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
    user_client = get_user_client()
    url: str | None = None
    storage_item: StorageItem | None = None

    if lr.data_link is not None and lr.data_link[:5] == "https":
        url = lr.data_link
    elif lr.backing_item_uuid is not None:
        storage_item = user_client.get_storage_item(lr.backing_item_uuid, sign_url=True)
        url = storage_item.get_signed_url()

    if lr.data_type == DataType.IMG_GROUP:
        if storage_item is None:
            """
            Fall back to "old school data fetching" when we don't know the storage item.
            Image groups will have: [None, list[Image]] 
            Image sequences will have: [Video, list[Image]]
            """
            #
            video_item, images_list = lr._project_client.get_data(lr.data_hash, get_signed_url=True)
            assert images_list is not None, "Images list should not be none for image groups."

            if video_item is not None and frame is None:
                # Image Sequence (whole video)
                url = video_item["data_link"]
            elif frame is not None:
                # Image Group or image sequence (single frame)
                url = images_list[frame].file_link
            else:
                raise NotImplementedError(DOWNLOAD_NATIVE_IMAGE_GROUP_WO_FRAME_ERROR_MESSAGE)
        else:
            """
            Leverage storage item to get the signed url.
            """
            if frame is None:
                # Can only download the whole image sequences - not image groups.
                if storage_item.item_type != StorageItemType.IMAGE_SEQUENCE:
                    raise NotImplementedError(DOWNLOAD_NATIVE_IMAGE_GROUP_WO_FRAME_ERROR_MESSAGE)
            else:
                if not lr.is_labelling_initialised:
                    lr.initialise_labels()
                storage_item = user_client.get_storage_item(lr.get_frame_view(frame).image_hash, sign_url=True)
                url = storage_item.get_signed_url()

    if url is None:
        raise ValueError("Failed to get a signed url for the asset")

    file_type, suffix = _guess_file_suffix(url, lr, storage_item)
    response = requests.get(url)
    response.raise_for_status()

    with TemporaryDirectory() as dir_name:
        dir_path = Path(dir_name)

        file_path = dir_path / f"{lr.data_hash}{suffix}"
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:
                    f.write(chunk)

        if file_type == "video" and frame is not None:  # Get that exact frame
            frame_content = get_frame(file_path, frame)
            frame_file = file_path.with_name(f"{file_path.name}_{frame}").with_suffix(".png")
            cv2.imwrite(frame_file.as_posix(), frame_content)
            file_path = frame_file

        yield file_path


T = TypeVar("T")


def batch_iterator(iterator: Iterable[T], batch_size: int) -> Iterable[List[T]]:
    """Yield batches of items from an iterator.

    Args:
        iterator: The source iterator
        batch_size: Size of each batch > 0

    Returns:
        Iterable of lists, each containing up to batch_size items
    """
    iterator = iter(iterator)  # Ensure we have an iterator
    while True:
        batch = []
        for _ in range(batch_size):
            try:
                batch.append(next(iterator))
            except StopIteration:
                break
        if not batch:
            break
        yield batch

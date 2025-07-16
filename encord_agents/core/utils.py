import logging
import mimetypes
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Generator, Iterable, List, TypeVar, cast

import requests
from encord.constants.enums import DataType
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.orm.storage import StorageItemType
from encord.storage import StorageItem
from encord.user_client import EncordUserClient

from encord_agents import __version__
from encord_agents.core.data_model import FrameData, LabelRowInitialiseLabelsArgs, LabelRowMetadataIncludeArgs
from encord_agents.core.settings import Settings

logger = logging.getLogger(__name__)

DOWNLOAD_NATIVE_IMAGE_GROUP_WO_FRAME_ERROR_MESSAGE = (
    "`frame` parameter set to None for a Native Image Group. "
    "Downloading entire native image group is currently not supported. "
    "Please contact Encord at support@encord.com for help or submit a PR with an implementation."
)


DOWNLOAD_GROUP_ERROR_MESSAGE = (
    "Downloading a group is currently not supported. "
    "We are considering what interface is most appropriate for combining groups and {editor/task} agents"
    "Please contact Encord at support@encord.com for help or submit a PR with an implementation."
)


def get_user_client(settings: Settings | None = None) -> EncordUserClient:
    """
    Generate an user client to access Encord.

    Returns:
        An EncordUserClient authenticated with the credentials from the encord_agents.core.settings.Settings.

    """
    settings = settings or Settings()
    return get_user_client_from_settings(settings)


@lru_cache(maxsize=1)
def get_user_client_from_settings(settings: Settings) -> EncordUserClient:
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
    DataType.NIFTI: "application/octet-stream",
    DataType.DICOM: "application/octet-stream",
    StorageItemType.VIDEO: "video/mp4",
    StorageItemType.AUDIO: "audio/mp3",
    StorageItemType.IMAGE_SEQUENCE: "video/mp4",
    StorageItemType.IMAGE: "image/png",
    StorageItemType.PDF: "application/pdf",
    StorageItemType.PLAIN_TEXT: "text/plain",
    StorageItemType.IMAGE_GROUP: "image/png",
    StorageItemType.NIFTI: "application/octet-stream",
}


def _guess_file_suffix(url: str, storage_item: StorageItem) -> tuple[str, str]:
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
    fallback_mimetype = _FALLBACK_MIMETYPES.get(storage_item.item_type, None)
    if fallback_mimetype is None:
        logger.warning(f"No fallback mimetype found for data type {storage_item.item_type}")

    mimetype = next(
        (
            t
            for t in (
                storage_item.mime_type,
                mimetypes.guess_type(url)[0],
                mimetypes.guess_type(storage_item.name)[0],
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
def download_asset(storage_item: StorageItem, frame: int | None = None) -> Generator[Path, None, None]:
    """
    Download the asset associated to a label row to disk.

    This function is a context manager. Data is cleaned up when the context is left.

    Example usage:

        with download_asset(storage_item, 10) as asset_path:
            # In here the file exists
            pixel_values = np.asarray(Image.open(asset_path))

    Args:
        storage_item: The Storage item for which you want to download the associated asset.
        frame: The frame that you need. If frame is none for a video, you the video path is returned.

    Raises:
        NotImplementedError: If you try to get all frames of an image group.
        ValueError: If you try to download an unsupported data type (e.g., DICOM).


    Yields:
        The file path for the requested asset.

    """
    url = storage_item.get_signed_url()

    if storage_item.item_type == StorageItemType.IMAGE_GROUP:
        if frame is None:
            # Can only download the whole image sequences - not image groups.
            raise NotImplementedError(DOWNLOAD_NATIVE_IMAGE_GROUP_WO_FRAME_ERROR_MESSAGE)

        child_storage_items = list(storage_item.get_child_items(get_signed_urls=True))
        assert len(child_storage_items) > frame, "The requested frame in the Image Group does not exist"
        url = child_storage_items[frame].get_signed_url()
    elif storage_item.item_type == StorageItemType.GROUP:
        raise NotImplementedError(DOWNLOAD_GROUP_ERROR_MESSAGE)

    if url is None:
        raise ValueError("Failed to get a signed url for the asset")

    file_type, suffix = _guess_file_suffix(url, storage_item)
    response = requests.get(url)
    response.raise_for_status()

    with TemporaryDirectory() as dir_name:
        dir_path = Path(dir_name)

        file_path = dir_path / f"{storage_item.uuid}{suffix}"
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:
                    f.write(chunk)

        if file_type == "video" and frame is not None:  # Get that exact frame
            from .video import get_frame, write_frame

            frame_content = get_frame(file_path, frame)
            frame_file = file_path.with_name(f"{file_path.name}_{frame}").with_suffix(".png")
            write_frame(frame_file, frame_content)
            file_path = frame_file

        yield file_path


def get_frame_count(storage_item: StorageItem) -> int:
    """
    Get the number of frames in a video.
    """
    if storage_item.item_type != StorageItemType.VIDEO:
        raise ValueError("This function only supports video storage items")
    if storage_item.frame_count is not None:
        return storage_item.frame_count
    if storage_item.duration is not None and storage_item.fps is not None:
        return int(storage_item.duration * storage_item.fps)
    raise ValueError("Frame count is not available for this storage item, missing: frame_count or duration and fps")


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

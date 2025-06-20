from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generator, Iterable, Iterator, Sequence

import numpy as np
from encord.exceptions import AuthenticationError, AuthorisationError, UnknownException
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.orm.storage import StorageItemType
from encord.storage import StorageItem
from encord.user_client import EncordUserClient
from encord.workflow.common import WorkflowTask
from encord.workflow.workflow import WorkflowStage
from numpy.typing import NDArray
from typing_extensions import Annotated

from encord_agents.core.data_model import Frame
from encord_agents.core.dependencies.models import Depends
from encord_agents.core.dependencies.shares import DataLookup
from encord_agents.core.utils import download_asset, get_frame_count, get_user_client
from encord_agents.exceptions import PrintableError


def dep_client() -> EncordUserClient:
    """
    Dependency to provide an authenticated user client.

    **Example:**

    ```python
    from encord.user_client import EncordUserClient
    from encord_agents.tasks.dependencies import dep_client
    ...
    @runner.stage("<my_stage_name>")
    def my_agent(
        client: Annotated[EncordUserClient, Depends(dep_client)]
    ) -> str:
        # Client is authenticated and ready to use.
        client.get_dataset("")
    ```

    """
    return get_user_client()


def dep_storage_item(storage_item: StorageItem) -> StorageItem:
    r"""
    Get the storage item associated with the underlying agent task.

    The [`StorageItem`](https://docs.encord.com/sdk-documentation/sdk-references/StorageItem){ target="\_blank", rel="noopener noreferrer" }
    is useful for multiple things like

    * Updating client metadata
    * Reading file properties like storage location, fps, duration, DICOM tags, etc.

    Note: When marking a task agent with the StorageItem dependency, we will bulk fetch the storage items for the tasks
    and then inject them independently with each task. Trivial method for backwards compatibility. Can do: storage_item: StorageItem directly

    **Example**

    ```python
    from encord.storage import StorageItem
    from encord_agents.tasks.dependencies import dep_storage_item

    @runner.stage(stage="<my_stage_name>")
    def my_agent(storage_item: Annotated[StorageItem, Depends(dep_storage_item)]) -> str:
        print(storage_item.name)
        print(storage_item.client_metadata)
        ...
    ```

    Args:
        storage_item: StorageItem

    Returns:
        The storage item.
    """
    return storage_item


def dep_single_frame(storage_item: StorageItem) -> NDArray[np.uint8]:
    """
    Dependency to inject the first frame of the underlying asset.

    The downloaded asset will be named `lr.data_hash.{suffix}`.
    When the function has finished, the downloaded file will be removed from the file system.

    **Example:**

    ```python
    from encord_agents import FrameData
    from encord_agents.tasks.dependencies import dep_single_frame
    ...

    @runner.stage("<my_stage_name>")
    def my_agent(
        frame: Annotated[NDArray[np.uint8], Depends(dep_single_frame)]
    ) -> str:
        assert frame.ndim == 3, "Will work"
    ```

    Args:
        storage_item: The Storage item. Automatically injected (see example above).

    Returns:
        Numpy array of shape [h, w, 3] RGB colors.

    """

    try:
        import cv2
    except ImportError:
        raise ImportError(
            "Your data agent is depending on computer vision capabilities and `opencv` is not installed. Please install either `opencv-python` or `opencv-python-headless`."
        )

    with download_asset(storage_item, frame=0) as asset:
        img = cv2.cvtColor(cv2.imread(asset.as_posix()), cv2.COLOR_BGR2RGB)

    return np.asarray(img, dtype=np.uint8)


def dep_video_iterator(storage_item: StorageItem) -> Generator[Iterator[Frame], None, None]:
    """
    Dependency to inject a video frame iterator for doing things over many frames.
    This uses OpenCV and the local backend on your machine.
    Decoding support may vary dependent on the video format, codec and your local configuration

    **Intended use**

    ```python
    from encord_agents import FrameData
    from encord_agents.tasks.dependencies import dep_video_iterator
    ...

    @runner.stage("<my_stage_name>")
    def my_agent(
        video_frames: Annotated[Iterator[Frame], Depends(dep_video_iterator)]
    ) -> str:
        for frame in video_frames:
            print(frame.frame, frame.content.shape)
    ```

    Args:
        storage_item: Automatically injected Storage item dependency.

    Raises:
        NotImplementedError: Will fail for other data types than video.

    Yields:
        An iterator.

    """
    from encord_agents.core.video import iter_video

    if storage_item.item_type != StorageItemType.VIDEO:
        raise NotImplementedError("`dep_video_iterator` only supported for video label rows")

    with download_asset(storage_item, None) as asset:
        yield iter_video(asset)


def dep_video_sampler(
    storage_item: StorageItem,
) -> Generator[Callable[[float | Sequence[int]], Iterable[Frame]], None, None]:
    """
    Dependency to inject a video sampler for doing things over many frames.
    This uses OpenCV and the local backend on your machine.
    Decoding support may vary dependent on the video format, codec and your local configuration.

    Args:
        storage_item: Automatically injected Storage item dependency.

    **Example:**

    ```python
    from encord_agents.tasks.dependencies import dep_video_sampler
    ...
    runner = Runner(project_hash="<project_hash_a>")

    @runner.stage("<stage_name_or_uuid>")
    def my_agent(
        video_sampler: Annotated[Callable[[float | Sequence[int]], Iterable[Frame]], Depends(dep_video_sampler)],
    ) -> str | None:
        for frame in video_sampler(1/5):
            # Get every 5th frame
            # i.e: [0,5,10,15,...]
        for frame in video_sampler([1, 2, 3]):
            # Get frames 1, 2, 3
        ...
    ```

    """
    from encord_agents.core.video import iter_video_with_indices

    if storage_item.item_type != StorageItemType.VIDEO:
        raise NotImplementedError("`dep_video_sampler` only supported for video label rows")

    with download_asset(storage_item, None) as asset:

        def video_sampler(
            frame_indexer: int | float | Sequence[int],
        ) -> Iterable[Frame]:
            """

            Args:
                frame_indexer (int | float | Iterable[int]):
                    * If int or float, the frame indexer is the frame sampling rate, e.g., 1/5 will return every 5th frame.
                    * If Iterable[int], the frame indexer is the list of frames to return.

            Returns:
                Iterable[Frame]: Iterates over the frames as described by the frame_indexer.
            """
            if isinstance(frame_indexer, (int, float)):
                # If frame_indexer is a float / int, it is the frame sampling rate
                # The larger the frame_indexer, the more frames you get
                if frame_indexer <= 0 or frame_indexer > 1:
                    raise ValueError("Frame sampling rate must be between 0 and 1")
                N_frames = get_frame_count(storage_item)
                frame_indices = [int(k / frame_indexer) for k in range(N_frames)]
            else:
                frame_indices = sorted(frame_indexer)

            def inner() -> Iterable[Frame]:
                yield from iter_video_with_indices(asset, frame_indices)

            return inner()

        yield video_sampler


def dep_asset(storage_item: StorageItem) -> Generator[Path, None, None]:
    """
    Get a local file path to data asset temporarily stored till end of task execution.

    This dependency fetches the underlying data asset based on a signed url.
    It temporarily stores the data on disk. Once the task is completed, the
    asset is removed from disk again.

    **Example:**

    ```python
    from encord_agents.tasks.dependencies import dep_asset
    ...
    runner = Runner(project_hash="<project_hash_a>")

    @runner.stage("<stage_name_or_uuid>")
    def my_agent(
        asset: Annotated[Path, Depends(dep_asset)],
    ) -> str | None:
        asset.stat()  # read file stats
        ...
    ```

    Returns:
        The path to the asset.

    Raises:
        ValueError: if the underlying assets are not videos, images, or audio.
        EncordException: if data type not supported by SDK yet.
    """
    with download_asset(storage_item) as asset:
        yield asset


@dataclass(frozen=True)
class Twin:
    """
    Dataclass to hold "label twin" information.
    """

    label_row: LabelRowV2
    task: WorkflowTask | None


def dep_twin_label_row(
    twin_project_hash: str, init_labels: bool = True, include_task: bool = False
) -> Callable[[LabelRowV2], Twin | None]:
    """
    Dependency to link assets between two Projects. When your `Runner` in running on
    `<project_hash_a>`, you can use this to get a `Twin` of labels and the underlying
    task in the "twin project" with `<project_hash_b>`.

    This is useful in situations like:

    * When you want to transfer labels from a source project" to a sink project.
    * If you want to compare labels to labels from other projects upon label submission.
    * If you want to extend an existing project with labels from another project on the same underlying data.

    **Example:**

    ```python
    from encord.workflow.common import WorkflowTask
    from encord.objects.ontology_labels_impl import LabelRowV2
    from encord_agents.tasks.dependencies import Twin, dep_twin_label_row
    ...
    runner = Runner(project_hash="<project_hash_a>")

    @runner.stage("<my_stage_name_in_project_a>")
    def my_agent(
        project_a_label_row: LabelRowV2,
        twin: Annotated[
            Twin, Depends(dep_twin_label_row(twin_project_hash="<project_hash_b>"))
        ],
    ) -> str | None:
        label_row_from_project_b: LabelRowV2 = twin.label_row
        task_from_project_b: WorkflowTask = instance.get_answer(attribute=checklist_attribute)
    ```

    Args:
        twin_project_hash: The project has of the twin project (attached to the same datasets)
            from which you want to load the additional data.
        init_labels: If true, the label row will be initialized before calling the agent.
        include_task: If true, the `task` field of the `Twin` will be populated. If population
            fails, e.g., for non-workflow projects, the task will also be None.

    Returns:
        The twin.

    Raises:
        encord.AuthorizationError: if you do not have access to the project.
    """
    client = get_user_client()
    try:
        twin_project = client.get_project(twin_project_hash)
    except (AuthorisationError, AuthenticationError):
        raise PrintableError(
            f"You do not seem to have access to the project with project hash `[blue]{twin_project_hash}[/blue]`"
        )
    except UnknownException:
        raise PrintableError(
            f"An unknown error occurred while trying to get the project with project hash `[blue]{twin_project_hash}[/blue]` in the `dep_twin_label_row` dependency."
        )

    label_rows: dict[str, LabelRowV2] = {lr.data_hash: lr for lr in twin_project.list_label_rows_v2()}

    def get_twin_label_row(lr_original: LabelRowV2) -> Twin | None:
        lr_twin = label_rows.get(lr_original.data_hash)
        if lr_twin is None:
            return None

        if init_labels:
            lr_twin.initialise_labels()

        graph_node = lr_twin.workflow_graph_node
        task: WorkflowTask | None = None

        if include_task and graph_node is not None:
            try:
                stage: WorkflowStage = twin_project.workflow.get_stage(uuid=graph_node.uuid)
                for task in stage.get_tasks(data_hash=lr_original.data_hash):
                    pass
            except Exception:
                # TODO: print proper warning.
                pass

        return Twin(label_row=lr_twin, task=task)

    return get_twin_label_row


def dep_data_lookup(lookup: Annotated[DataLookup, Depends(DataLookup.sharable)]) -> DataLookup:
    """
    Get a lookup to easily retrieve data rows and storage items associated with the given task.

    !!! warning "Deprecated"
        `dep_data_lookup` is deprecated and will be removed in version 0.2.10.
        Use `dep_storage_item` instead for accessing storage items.

    **Migration Guide:**

    ```python
    # Old way (deprecated)
    from encord_agents.tasks.dependencies import dep_data_lookup, DataLookup

    @runner.stage(stage="Agent 1")
    def my_agent(
        task: AgentTask,
        lookup: Annotated[DataLookup, Depends(dep_data_lookup)]
    ) -> str:
        storage_item = lookup.get_storage_item(task.data_hash)
        client_metadata = storage_item.client_metadata
        ...

    # New way (recommended)
    from encord_agents.tasks.dependencies import dep_storage_item

    @runner.stage(stage="Agent 1")
    def my_agent(
        task: AgentTask,
        storage_item: Annotated[StorageItem, Depends(dep_storage_item)]
    ) -> str:
        # storage_item is directly available
        client_metadata = storage_item.client_metadata

        # Update metadata
        storage_item.update(
            client_metadata={
                "new": "entry",
                **(client_metadata or {})
            }
        )
        ...
    ```

    Args:
        lookup: The object that you can use to lookup data rows and storage items. Automatically injected.

    Returns:
        The (shared) lookup object.

    """
    import warnings

    warnings.warn(
        "dep_data_lookup is deprecated and will be removed in version 0.2.10. "
        "Use 'dep_storage_item' instead for accessing storage items. "
        "See the function docstring for migration examples.",
        DeprecationWarning,
        stacklevel=2,
    )
    return lookup

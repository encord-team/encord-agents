from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generator, Iterator

import cv2
import numpy as np
from encord.constants.enums import DataType
from encord.exceptions import AuthenticationError, AuthorisationError
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.project import Project
from encord.storage import StorageItem
from encord.user_client import EncordUserClient
from encord.workflow.common import WorkflowTask
from encord.workflow.stages.agent import AgentTask
from encord.workflow.workflow import WorkflowStage
from numpy.typing import NDArray
from typing_extensions import Annotated

from encord_agents.core.data_model import Frame
from encord_agents.core.dependencies.models import Depends
from encord_agents.core.dependencies.shares import DataLookup
from encord_agents.core.utils import download_asset, get_user_client
from encord_agents.core.video import iter_video
from encord_agents.exceptions import PrintableError


def dep_client() -> EncordUserClient:
    """
    Dependency to provide an authenticated user client.

    **Example:**

    ```python
    from encord.user_client import EncordUserClient
    from encord_agents.tasks.depencencies import dep_client
    ...
    @runner.stage("<my_stage_name>")
    def my_agent(
        client: Annotated[EncordUserClient, Depends(dep_client)]
    ) -> str:
        # Client will authenticated and ready to use.
        client.get_dataset("")
    ```

    """
    return get_user_client()


def dep_single_frame(lr: LabelRowV2) -> NDArray[np.uint8]:
    """
    Dependency to inject the first frame of the underlying asset.

    The downloaded asset will be named `lr.data_hash.{suffix}`.
    When the function has finished, the downloaded file will be removed from the file system.

    **Example:**

    ```python
    from encord_agents import FrameData
    from encord_agents.tasks.depencencies import dep_single_frame
    ...

    @runner.stage("<my_stage_name>")
    def my_agent(
        lr: LabelRowV2,  # <- Automatically injected
        frame: Annotated[NDArray[np.uint8], Depends(dep_single_frame)]
    ) -> str:
        assert frame.ndim == 3, "Will work"
    ```

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

    **Intended use**

    ```python
    from encord_agents import FrameData
    from encord_agents.tasks.depencencies import dep_video_iterator
    ...

    @runner.stage("<my_stage_name>")
    def my_agent(
        lr: LabelRowV2,  # <- Automatically injected
        video_frames: Annotated[Iterator[Frame], Depends(dep_video_iterator)]
    ) -> str:
        for frame in video_frames:
            print(frame.frame, frame.content.shape)
    ```

    Args:
        lr: Automatically injected label row dependency.

    Raises:
        NotImplementedError: Will fail for other data types than video.

    Yields:
        An iterator.

    """
    if not lr.data_type == DataType.VIDEO:
        raise NotImplementedError("`dep_video_iterator` only supported for video label rows")

    with download_asset(lr, None) as asset:
        yield iter_video(asset)


def dep_asset(lr: LabelRowV2) -> Generator[Path, None, None]:
    """
    Get a local file path to data asset temporarily stored till end of task execution.

    This dependency will fetch the underlying data asset based on a signed url.
    It will temporarily store the data on disk. Once the task is completed, the
    asset will be removed from disk again.

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
        `ValueError` if the underlying assets are not videos, images, or audio.
        `EncordException` if data type not supported by SDK yet.
    """
    with download_asset(lr) as asset:
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
            failes, e.g., for non-workflow projects, the task will also be None.

    Returns:
        The twin.

    Raises:
        `encord.AuthorizationError` if you do not have access to the project.
    """
    client = get_user_client()
    try:
        twin_project = client.get_project(twin_project_hash)
    except (AuthorisationError, AuthenticationError):
        raise PrintableError(
            f"You do not seem to have access to the project with project hash `[blue]{twin_project_hash}[/blue]`"
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

    !!! info
        If you're just looking to get the associated storage item to a task, consider using `dep_storage_item` instead.


    The lookup can, e.g., be useful for

    * Updating client metadata
    * Downloading data from signed urls
    * Matching data to other projects

    **Example:**

    ```python
    from encord.orm.dataset import DataRow
    from encord.stotage import StorageItem
    from encord.workflow.stages.agent import AgentTask

    @runner.stage(stage="Agent 1")
    def my_agent(
        task: AgentTask,
        lookup: Annotated[DataLookup, Depends(dep_data_lookup)]
    ) -> str:
        # Data row from the underlying dataset
        data_row: DataRow = lookup.get_data_row(task.data_hash)

        # Storage item from Encord Index
        storage_item: StorageItem = lookup.get_storage_item(task.data_hash)

        # Current metadata
        client_metadata = storage_item.client_metadata

        # Update metadata
        storage_item.update(
            client_metadata={
                "new": "entry",
                **(client_metadata or {})
            }
        )  # metadata. Make sure not to update in place!
        ...
    ```


    Args:
        lookup: The object that you can use to lookup data rows and storage items. Automatically injected.

    Returns:
        The (shared) lookup object.

    """
    return lookup


def dep_storage_item(lookup: Annotated[DataLookup, Depends(dep_data_lookup)], task: AgentTask) -> StorageItem:
    r"""
    Get the storage item associated with the underlying agent task.

    The [`StorageItem`](https://docs.encord.com/sdk-documentation/sdk-references/StorageItem){ target="\_blank", rel="noopener noreferrer" }
    is useful for multiple things like

    * Updating client metadata
    * Reading file properties like storage location, fps, duration, DICOM tags, etc.

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

    """
    return lookup.get_storage_item(task.data_hash)

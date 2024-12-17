"""
Dependencies for injection in GCP Cloud run functions.

This module contains dependencies that you can inject within your cloud functions.
Dependencies that depend on others don't need to be used together. They'll
work just fine alone.

Note that you can also use the following _typed_ parameters. If the type annotations
are not present, the injection mechanism cannot resolve the them:

```python
from encord.project import Project
from encord.objects.ontology_labels_impl import LabelRowV2
from encord_agents import FrameData
...
@app.post("/my-agent-route")
def my_agent(
    frame_data: FrameData,
    project: Project,
    label_row: LabelRowV2,
):
    ...
```

- [`FrameData`](../../reference/core/#encord_agents.core.data_model.FrameData) is automatically injected via the api request body.
- [`Project`](https://docs.encord.com/sdk-documentation/sdk-references/project){ target="_blank", rel="noopener noreferrer" } is automatically loaded based on the frame data.
- [`label_row_v2`](https://docs.encord.com/sdk-documentation/sdk-references/LabelRowV2) is automatically loaded based on the frame data.
"""

from pathlib import Path
from typing import Callable, Generator, Iterator

import cv2
import numpy as np
from encord.constants.enums import DataType
from encord.objects.common import Shape
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.ontology_object import Object
from encord.storage import StorageItem
from encord.user_client import EncordUserClient
from numpy.typing import NDArray
from typing_extensions import Annotated

from encord_agents.core.data_model import Frame, FrameData, InstanceCrop
from encord_agents.core.dependencies.models import Depends
from encord_agents.core.dependencies.shares import DataLookup
from encord_agents.core.utils import download_asset, get_user_client
from encord_agents.core.video import iter_video
from encord_agents.core.vision import crop_to_object


def dep_client() -> EncordUserClient:
    """
    Dependency to provide an authenticated user client.

    **Example:**

    ```python
    from encord.user_client import EncordUserClient
    from encord_agents.gcp import editor_agent
    from encord_agents.gcp.dependencies import dep_client
    ...
    @editor_agent()
    def (
        client: Annotated[EncordUserClient, Depends(dep_client)]
    ):
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
    from encord_agents.gcp import editor_agent
    from encord_agents.gcp.dependencies import dep_single_frame
    ...

    @editor_agent()
    def my_agent(
        frame: Annotated[NDArray[np.uint8], Depends(dep_single_frame)]
    ):
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


def dep_asset(lr: LabelRowV2) -> Generator[Path, None, None]:
    """
    Get a local file path to data asset temporarily stored till end of agent execution.

    This dependency will fetch the underlying data asset based on a signed url.
    It will temporarily store the data on disk. Once the task is completed, the
    asset will be removed from disk again.

    **Example:**

    ```python
    from encord_agents.gcp import editor_agent
    from encord_agents.gcp.dependencies import dep_asset
    ...
    runner = Runner(project_hash="<project_hash_a>")

    @editor_agent()
    def my_agent(
        asset: Annotated[Path, Depends(dep_asset)]
    ) -> None:
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


def dep_video_iterator(lr: LabelRowV2) -> Generator[Iterator[Frame], None, None]:
    """
    Dependency to inject a video frame iterator for doing things over many frames.

    **Example:**

    ```python
    from encord_agents import FrameData
    from encord_agents.gcp import editor_agent
    from encord_agents.gcp.dependencies import dep_video_iterator
    ...

    @editor_agent()
    def my_agent(
        video_frames: Annotated[Iterator[Frame], Depends(dep_video_iterator)]
    ):
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
    from typing_extensions import Annotated
    from encord.storage import StorageItem
    from encord_agents import FrameData
    from encord_agents.gcp import editor_agent, Depends
    from encord_agents.gcp.dependencies import DataLookup, dep_data_lookup

    @editor_agent()
    def my_agent(
        frame_data: FrameData,
        lookup: Annotated[DataLookup, Depends(dep_data_lookup)]
    ):
        print("data hash", lookup.get_data_row(frame_data.data_hash))
        print("storage item", lookup.get_storage_item(frame_data.data_hash))
        ...


    ```


    Args:
        lookup: The object that you can use to lookup data rows and storage items. Automatically injected.

    Returns:
        The (shared) lookup object.

    """
    return lookup


def dep_storage_item(
    lookup: Annotated[DataLookup, Depends(dep_data_lookup)],
    frame_data: FrameData,
) -> StorageItem:
    r"""
    Get the storage item associated with the underlying agent task.

    The [`StorageItem`](https://docs.encord.com/sdk-documentation/sdk-references/StorageItem){ target="\_blank", rel="noopener noreferrer" }
    is useful for multiple things like

    * Updating client metadata
    * Reading file properties like storage location, fps, duration, DICOM tags, etc.

    **Example**

    ```python
    from typing_extensions import Annotated
    from encord.storage import StorageItem
    from encord_agents.gcp import editor_agent, Depends
    from encord_agents.gcp.dependencies import dep_storage_item


    @editor_agent()
    def my_agent(storage_item: Annotated[StorageItem, Depends(dep_storage_item)]):
        print("uuid", storage_item.uuid)
        print("client_metadata", storage_item.client_metadata)
        ...
    ```

    """
    return lookup.get_storage_item(frame_data.data_hash)


def dep_object_crops(
    filter_ontology_objects: list[Object | str] | None = None,
) -> Callable[[FrameData, LabelRowV2, NDArray[np.uint8]], list[InstanceCrop]]:
    """
    Get a list of object instances and frame crops associated with each object.

    Useful, e.g., to be able to run each crop against a model.

    **Example:**

    ```python
    @editor_agent
    def my_agent(crops: Annotated[list[InstanceCrop], Depends[dep_object_crops(filter_ontology_objects=["eBw/75bg"])]]):
        for crop in crops:
            crop.content  # <- this is raw numpy rgb values
            crop.frame    # <- this is the frame number in video
            crop.instance # <- this is the object instance from the label row
            crop.b64_encoding()  # <- a base64 encoding of the image content
        ...
    ```

    Args:
        filter_ontology_objects: Specify a list of ontology objects to include.
            If provided, only instances of these object types will be included.
            Strings are matched against `feature_node_hashes`.


    Returns: The dependency to be injected into the cloud function.

    """
    legal_feature_hashes = {
        o.feature_node_hash if isinstance(o, Object) else o for o in (filter_ontology_objects or [])
    }

    def _dep_object_crops(
        frame_data: FrameData, lr: LabelRowV2, frame: Annotated[NDArray[np.uint8], Depends(dep_single_frame)]
    ) -> list[InstanceCrop]:
        legal_shapes = {Shape.POLYGON, Shape.BOUNDING_BOX, Shape.ROTATABLE_BOUNDING_BOX, Shape.BITMASK}
        return [
            InstanceCrop(
                frame=frame_data.frame,
                content=crop_to_object(frame, o.get_annotation(frame=frame_data.frame).coordinates),  # type: ignore
                instance=o,
            )
            for o in lr.get_object_instances(filter_frames=frame_data.frame)
            if o.ontology_item.shape in legal_shapes
            and (not legal_feature_hashes or o.feature_hash in legal_feature_hashes)
        ]

    return _dep_object_crops

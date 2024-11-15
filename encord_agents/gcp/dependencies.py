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

from typing import Generator, Iterator

import cv2
import numpy as np
from encord.constants.enums import DataType
from encord.objects.common import Shape
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.ontology_object_instance import ObjectInstance
from encord.storage import StorageItem
from encord.user_client import EncordUserClient
from numpy.typing import NDArray
from typing_extensions import Annotated

from encord_agents.core.data_model import Frame, FrameData
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


def dep_video_iterator(lr: LabelRowV2) -> Generator[Iterator[Frame], None, None]:
    """
    Dependency to inject a video frame iterator for doing things over many frames.

    **Intended use**

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

def dep_object_crops(frame_data: FrameData, lr: LabelRowV2, frame: Annotated[NDArray[np.uint8], Depends(dep_single_frame)]) -> list[tuple[ObjectInstance, NDArray[np.uint8]]]:
    """
    Get a list of object instances and crops associated with each object.

    Useful, e.g., to be able to run each crop against a model.

    Args:
        frame_data: The frame data from the label editor
        lr: The associated label row
        frame: The actual pixel values

    Returns: Tuples of object instances and their respective image crops.

    """
    return [
        (
            o,
            crop_to_object(frame, o.get_annotation(frame=frame_data.frame).coordinates),  # type: ignore
        )
        for o in lr.get_object_instances(filter_frames=frame_data.frame)
        if o.ontology_item.shape in {Shape.POLYGON, Shape.BOUNDING_BOX, Shape.ROTATABLE_BOUNDING_BOX, Shape.BITMASK}
    ]



"""
Dependencies for injection in FastAPI servers.

This module contains dependencies that you can inject within your api routes.
Dependencies that depend on others don't need to be used together. They'll
work just fine alone.

Note that you can also use the function parameter:
```python
from typing_extensions import Annotated
from fastapi import Form
from encord_agents import FrameData
...
@app.post("/my-agent-route")
def my_agent(
    frame_data: FrameData,
):
    ...
```
[`FrameData`](../../reference/core/#encord_agents.core.data_model.FrameData) is automatically injected via the api request body.

"""

from pathlib import Path
from typing import Annotated, Callable, Generator, Iterator

import cv2
import numpy as np
from encord.constants.enums import DataType
from encord.objects.common import Shape
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.ontology_object import Object
from encord.project import Project
from encord.storage import StorageItem
from encord.user_client import EncordUserClient
from numpy.typing import NDArray

from encord_agents.core.data_model import LabelRowInitialiseLabelsArgs, LabelRowMetadataIncludeArgs
from encord_agents.core.dependencies.shares import DataLookup
from encord_agents.core.vision import crop_to_object

try:
    from fastapi import Depends, Form
except ModuleNotFoundError:
    print(
        'To use the `fastapi` dependencies, you must also install fastapi. `python -m pip install "fastapi[standard]"'
    )
    exit()

from encord_agents.core.data_model import Frame, FrameData, InstanceCrop
from encord_agents.core.utils import (
    download_asset,
    get_initialised_label_row,
    get_user_client,
)
from encord_agents.core.video import iter_video


def dep_client() -> EncordUserClient:
    """
    Dependency to provide an authenticated user client.

    **Example**:

    ```python
    from encord.user_client import EncordUserClient
    from encord_agents.fastapi.depencencies import dep_client
    ...
    @app.post("/my-route")
    def my_route(
        client: Annotated[EncordUserClient, Depends(dep_client)]
    ):
        # Client will authenticated and ready to use.
    ```

    """
    return get_user_client()


def dep_label_row_with_args(
    label_row_metadata_include_args: LabelRowMetadataIncludeArgs | None = None,
    label_row_initialise_labels_args: LabelRowInitialiseLabelsArgs | None = None,
) -> Callable[[FrameData], LabelRowV2]:
    """
    Dependency to provide an initialized label row.

    **Example:**

    ```python
    from encord_agents.core.data_model import LabelRowMetadataIncludeArgs, LabelRowInitialiseLabelsArgs
    from encord_agents.fastapi.depencencies import dep_label_row_with_args
    ...

    include_args = LabelRowMetadataIncludeArgs(
        include_client_metadata=True,
        include_workflow_graph_node=True,
    )
    init_args = LabelRowInitialiseLabelsArgs(
        include_signed_url=True,
    )

    @app.post("/my-route")
    def my_route(
        lr: Annotated[LabelRowV2, Depends(dep_label_row_with_args(include_args, init_args))]
    ):
        assert lr.is_labelling_initialised  # will work
        assert lr.client_metadata           # will be available if set already
    ```

    Args:
        frame_data: the frame data from the route. This parameter is automatically injected
            if it's a part of your route (see example above)


    Returns:
        The initialized label row.

    """

    def wrapper(frame_data: FrameData) -> LabelRowV2:
        return get_initialised_label_row(
            frame_data, include_args=label_row_metadata_include_args, init_args=label_row_initialise_labels_args
        )

    return wrapper


def dep_label_row(frame_data: FrameData) -> LabelRowV2:
    """
    Dependency to provide an initialized label row.

    **Example:**

    ```python
    from encord_agents.fastapi.depencencies import dep_label_row
    ...


    @app.post("/my-route")
    def my_route(
        lr: Annotated[LabelRowV2, Depends(dep_label_row)]
    ):
        assert lr.is_labelling_initialised  # will work
    ```

    Args:
        frame_data: the frame data from the route. This parameter is automatically injected
            if it's a part of your route (see example above)

    Returns:
        The initialized label row.

    """
    return get_initialised_label_row(frame_data)


def dep_single_frame(lr: Annotated[LabelRowV2, Depends(dep_label_row)], frame_data: FrameData) -> NDArray[np.uint8]:
    """
    Dependency to inject the underlying asset of the frame data.

    The downloaded asset will be named `lr.data_hash.{suffix}`.
    When the function has finished, the downloaded file will be removed from the file system.

    **Example:**

    ```python
    from encord_agents.fastapi.depencencies import dep_single_frame
    ...

    @app.post("/my-route")
    def my_route(
        frame: Annotated[NDArray[np.uint8], Depends(dep_single_frame)]
    ):
        assert arr.ndim == 3, "Will work"
    ```

    Args:
        lr: The label row. Automatically injected (see example above).
        frame_data: the frame data from the route. This parameter is automatically injected
            if it's a part of your route (see example above).

    Returns: Numpy array of shape [h, w, 3] RGB colors.

    """
    with download_asset(lr, frame_data.frame) as asset:
        img = cv2.cvtColor(cv2.imread(asset.as_posix()), cv2.COLOR_BGR2RGB)
    return np.asarray(img, dtype=np.uint8)


def dep_asset(
    lr: Annotated[
        LabelRowV2,
        Depends(
            dep_label_row_with_args(
                label_row_initialise_labels_args=LabelRowInitialiseLabelsArgs(include_signed_url=True)
            )
        ),
    ],
) -> Generator[Path, None, None]:
    """
    Get a local file path to data asset temporarily stored till end of agent execution.

    This dependency will fetch the underlying data asset based on a signed url.
    It will temporarily store the data on disk. Once the task is completed, the
    asset will be removed from disk again.

    **Example:**

    ```python
    from encord_agents.fastapi.depencencies import dep_asset
    ...
    runner = Runner(project_hash="<project_hash_a>")

    @app.post("/my-route")
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


def dep_video_iterator(lr: Annotated[LabelRowV2, Depends(dep_label_row)]) -> Generator[Iterator[Frame], None, None]:
    """
    Dependency to inject a video frame iterator for doing things over many frames.

    **Example:**

    ```python
    from encord_agents.fastapi.depencencies import dep_video_iterator, Frame
    ...

    @app.post("/my-route")
    def my_route(
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


def dep_project(frame_data: FrameData, client: Annotated[EncordUserClient, Depends(dep_client)]) -> Project:
    r"""
    Dependency to provide an instantiated
    [Project](https://docs.encord.com/sdk-documentation/sdk-references/LabelRowV2){ target="\_blank", rel="noopener noreferrer" }.

    **Example:**

    ```python
    from encord.project import Project
    from encord_agents.fastapi.depencencies import dep_project
    ...
    @app.post("/my-route")
    def my_route(
        project: Annotated[Project, Depends(dep_project)]
    ):
        # Project will authenticated and ready to use.
        print(project.title)
    ```


    Args:
        frame_data:
        client:

    Returns:

    """
    return client.get_project(project_hash=frame_data.project_hash)


def _lookup_adapter(project: Annotated[Project, Depends(dep_project)]) -> DataLookup:
    return DataLookup.sharable(project)


def dep_data_lookup(lookup: Annotated[DataLookup, Depends(_lookup_adapter)]) -> DataLookup:
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
    from fastapi import Form
    from typing_extensions import Annotated
    from encord_agents import FrameData
    from encord_agents.fastapi.dependencies import dep_data_lookup, DataLookup

    ...
    @app.post("/my-agent")
    def my_agent(
        frame_data: FrameData,
        lookup: Annotated[DataLookup, Depends(dep_data_lookup)]
    ):
        # Client will authenticated and ready to use.
        print(lookup.get_data_row(frame_data.data_hash).title)
        print(lookup.get_storage_item(frame_data.data_hash).client_metadata)
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
    from encord.storage import StorageItem
    from encord_agents.fastapi.dependencies import dep_storage_item

    @app.post("/my-agent")
    def my_agent(
        storage_item: Annotated[StorageItem, Depends(dep_storage_item)]
    ):
        # Client will authenticated and ready to use.
        print(storage_item.dicom_study_uid)
        print(storage_item.client_metadata)
    ```

    """
    return lookup.get_storage_item(frame_data.data_hash)


def dep_object_crops(
    filter_ontology_objects: list[Object | str] | None = None,
) -> Callable[[FrameData, LabelRowV2, NDArray[np.uint8]], list[InstanceCrop]]:
    """
    Create a dependency that provides crops of object instances.

    Useful, e.g., to be able to run each crop against a model.

    **Example:**

    ```python
    @app.post("/object_classification")
    async def classify_objects(
        crops: Annotated[
            list[InstanceCrop],
            Depends(dep_object_crops(filter_ontology_objects=[generic_ont_obj])),
        ],
    ):
        for crop in crops:
            crop.content  # <- this is raw numpy rgb values
            crop.frame    # <- this is the frame number in video
            crop.instance # <- this is the object instance from the label row
            crop.b64_encoding()  # <- a base64 encoding of the image content
        ...
    ```

    Args:
        filter_ontology_objects: Optional list of ontology objects to filter by.
            If provided, only instances of these object types will be included.
            Strings are matched against `feature_node_hashes`.

    Returns:
        A FastAPI dependency function that yields a list of InstanceCrop.
    """
    legal_feature_hashes = {
        o.feature_node_hash if isinstance(o, Object) else o for o in (filter_ontology_objects or [])
    }

    def _dep_object_crops(
        frame_data: FrameData,
        lr: Annotated[LabelRowV2, Depends(dep_label_row)],
        frame: Annotated[NDArray[np.uint8], Depends(dep_single_frame)],
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

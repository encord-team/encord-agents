import os
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Iterator, NamedTuple
from uuid import UUID

import numpy as np
import pytest
from encord.constants.enums import DataType
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.orm.storage import StorageItemType
from encord.project import Project
from encord.storage import StorageItem
from encord.user_client import EncordUserClient
from encord.workflow.stages.agent import AgentStage, AgentTask
from typing_extensions import Annotated

from encord_agents.core.data_model import Frame
from encord_agents.core.dependencies.models import Depends
from encord_agents.core.utils import DOWNLOAD_NATIVE_IMAGE_GROUP_WO_FRAME_ERROR_MESSAGE
from encord_agents.exceptions import PrintableError
from encord_agents.tasks.dependencies import (
    Twin,
    dep_asset,
    dep_client,
    dep_single_frame,
    dep_storage_item,
    dep_twin_label_row,
    dep_video_iterator,
    dep_video_sampler,
)


class SharedTaskDependencyResolutionContext(NamedTuple):
    project: Project
    video_label_row: LabelRowV2
    image_label_row: LabelRowV2
    image_group_label_row: LabelRowV2
    image_sequence_label_row: LabelRowV2
    twin_project: Project
    pdf_label_row: LabelRowV2
    plain_text_label_row: LabelRowV2
    audio_label_row: LabelRowV2
    video_storage_item: StorageItem
    image_storage_item: StorageItem
    image_group_storage_item: StorageItem
    image_sequence_storage_item: StorageItem
    plain_text_storage_item: StorageItem
    pdf_storage_item: StorageItem
    audio_storage_item: StorageItem
    # dicom_file_label_row: LabelRowV2
    # dicom_series_label_row: LabelRowV2
    # nifti_label_row: LabelRowV2


# Load project info once for the class
@pytest.fixture(scope="class")
def context(
    user_client: EncordUserClient, class_level_ephemeral_project_hash: str, class_level_ephemeral_twin_project_hash: str
) -> SharedTaskDependencyResolutionContext:
    """
    Load project info once for the class.
    """
    project = user_client.get_project(class_level_ephemeral_project_hash)
    twin_project = user_client.get_project(class_level_ephemeral_twin_project_hash)
    label_rows = project.list_label_rows_v2()
    storage_items = {
        si.uuid: si
        for si in user_client.get_storage_items(
            item_uuids=[lr.backing_item_uuid for lr in label_rows if lr.backing_item_uuid is not None], sign_url=True
        )
    }

    image_label_row = next((lr for lr in label_rows if lr.data_type == DataType.IMAGE))
    video_label_row = next((lr for lr in label_rows if lr.data_type == DataType.VIDEO))
    image_group_label_row = next(
        (lr for lr in label_rows if storage_items[lr.backing_item_uuid].item_type == StorageItemType.IMAGE_GROUP)  # type: ignore[index]
    )
    image_sequence_label_row = next(
        (lr for lr in label_rows if storage_items[lr.backing_item_uuid].item_type == StorageItemType.IMAGE_SEQUENCE)  # type: ignore[index]
    )
    pdf_label_row = next((lr for lr in label_rows if lr.data_type == DataType.PDF))
    plain_text_label_row = next((lr for lr in label_rows if lr.data_type == DataType.PLAIN_TEXT))
    audio_label_row = next((lr for lr in label_rows if lr.data_type == DataType.AUDIO))

    assert image_label_row is not None
    assert video_label_row is not None
    assert image_group_label_row is not None
    assert image_sequence_label_row is not None
    assert pdf_label_row is not None
    assert plain_text_label_row is not None
    assert audio_label_row is not None

    return SharedTaskDependencyResolutionContext(
        project=project,
        twin_project=twin_project,
        image_label_row=image_label_row,
        video_label_row=video_label_row,
        image_group_label_row=image_group_label_row,
        image_sequence_label_row=image_sequence_label_row,
        pdf_label_row=pdf_label_row,
        plain_text_label_row=plain_text_label_row,
        audio_label_row=audio_label_row,
        video_storage_item=storage_items[video_label_row.backing_item_uuid or UUID(int=0)],
        image_storage_item=storage_items[image_label_row.backing_item_uuid or UUID(int=0)],
        image_group_storage_item=storage_items[image_group_label_row.backing_item_uuid or UUID(int=0)],
        image_sequence_storage_item=storage_items[image_sequence_label_row.backing_item_uuid or UUID(int=0)],
        pdf_storage_item=storage_items[pdf_label_row.backing_item_uuid or UUID(int=0)],
        plain_text_storage_item=storage_items[plain_text_label_row.backing_item_uuid or UUID(int=0)],
        audio_storage_item=storage_items[audio_label_row.backing_item_uuid or UUID(int=0)],
    )


class TestDependencyResolution:
    context: SharedTaskDependencyResolutionContext

    @classmethod
    @pytest.fixture(autouse=True)
    def setup(cls, context: SharedTaskDependencyResolutionContext) -> None:
        # Ensure that the user_client can authenticate
        cls.context = context

    # Set the project and first label row for the class
    @staticmethod
    def test_dep_client() -> None:
        client = dep_client()
        assert isinstance(client, EncordUserClient)

    def test_dep_single_frame(self) -> None:
        def _test_dep_single_frame(storage_item: StorageItem) -> None:
            frame = dep_single_frame(storage_item)
            assert isinstance(frame, np.ndarray)
            assert frame.ndim == 3  # Height, width, channels
            assert frame.dtype == np.uint8

            if storage_item.item_type == StorageItemType.IMAGE_GROUP:
                first_frame = next(iter(storage_item.get_child_items()))
                height, width = first_frame.height, first_frame.width
            else:
                height, width = storage_item.height, storage_item.width
            assert frame.shape == (height, width, 3)

        _test_dep_single_frame(self.context.video_storage_item)
        _test_dep_single_frame(self.context.image_storage_item)
        _test_dep_single_frame(self.context.image_group_storage_item)
        _test_dep_single_frame(self.context.image_sequence_storage_item)

    def test_dep_video_iterator(self) -> None:
        # Test that the error is raised for non-video label rows
        assert self.context.image_storage_item.item_type != StorageItemType.VIDEO
        with pytest.raises(NotImplementedError) as e:
            next(dep_video_iterator(self.context.image_storage_item))
        assert str(e.value) == "`dep_video_iterator` only supported for video label rows"

        # Test that the iterator is returned for video label rows
        video_gen = dep_video_iterator(self.context.video_storage_item)
        video_iter = next(video_gen)
        assert isinstance(video_iter, Iterator)

        first_frame: Frame | None = None
        counter = 0
        for i, frame in enumerate(video_iter):
            # Check last frame
            if first_frame is None:
                first_frame = frame
            assert isinstance(frame, Frame)
            assert isinstance(frame.content, np.ndarray)
            assert frame.content.ndim == 3
            assert frame.frame == i
            counter += 1

        assert counter == self.context.video_label_row.number_of_frames

        # Check equal to dep_single_frame
        assert first_frame is not None
        dep_single_frame_frame = dep_single_frame(self.context.video_storage_item)
        assert np.array_equal(first_frame.content, dep_single_frame_frame)

    def test_dep_video_sampler(self) -> None:
        video_sampler_gen = dep_video_sampler(self.context.video_storage_item)
        video_sampler = next(video_sampler_gen)

        # Call with int
        frames = video_sampler(1)
        assert isinstance(frames, Iterator)
        assert abs(len(list(frames)) - self.context.video_label_row.number_of_frames) <= 1

        # Call with float
        frames = video_sampler(0.5)
        assert isinstance(frames, Iterator)
        assert abs(len(list(frames)) - self.context.video_label_row.number_of_frames // 2) <= 1

        with pytest.raises(ValueError):
            video_sampler(0)
        with pytest.raises(ValueError):
            video_sampler(1.5)

        # Call with list
        frames = video_sampler([1, 2, 3])
        assert isinstance(frames, Iterator)
        frames_list = list(frames)
        assert len(frames_list) == 3
        assert [frame.frame for frame in frames_list] == [1, 2, 3]

        # Test that the sampler aligns with the iterator
        video_iter_gen = dep_video_iterator(self.context.video_storage_item)
        video_frames = next(video_iter_gen)
        for sampler_frame, video_frame in zip(video_sampler([0, 1, 2]), video_frames, strict=False):
            assert sampler_frame.frame == video_frame.frame
            assert np.equal(sampler_frame.content, video_frame.content).all()

        # Test non-trvial float aligns with previous behaviour
        frames_from_sampler = video_sampler(0.5)
        video_iter_gen = dep_video_iterator(self.context.video_storage_item)
        video_frames = next(video_iter_gen)

        for frame_from_sampler in frames_from_sampler:
            frame_from_video = next(video_frames)
            assert frame_from_sampler.frame == frame_from_video.frame
            assert np.equal(frame_from_sampler.content, frame_from_video.content).all()
            # Step video_iter_gen 1/0.5 = 2x
            next(video_frames)

    def test_dep_asset(self) -> None:
        """
        We need to employ a context manager to ensure that the asset is cleaned up after the test.
        This happens under the hood when we use `solve_generator` in `get_field_values`.
        In turn, it happens when you use the gcp wrapper, the task runners, etc. that resolve dependencies.
        """
        with ExitStack() as stack:

            def _test_dep_asset(storage_item: StorageItem, suffix: str) -> Path:
                cm = contextmanager(dep_asset)(storage_item)
                asset_path = stack.enter_context(cm)
                assert isinstance(asset_path, Path)
                assert asset_path.suffix == suffix, f"{asset_path.suffix=} != {suffix=}"
                assert asset_path.exists()
                return asset_path

            pdf_path = _test_dep_asset(self.context.pdf_storage_item, ".pdf")
            plain_text_path = _test_dep_asset(self.context.plain_text_storage_item, ".txt")
            audio_path = _test_dep_asset(self.context.audio_storage_item, ".mp3")
            video_path = _test_dep_asset(self.context.video_storage_item, ".mp4")
            image_path = _test_dep_asset(self.context.image_storage_item, ".jpeg")
            image_sequence_path = _test_dep_asset(self.context.image_sequence_storage_item, ".mp4")

        assert not pdf_path.exists()
        assert not plain_text_path.exists()
        assert not audio_path.exists()
        assert not video_path.exists()
        assert not image_path.exists()
        assert not image_sequence_path.exists()

        # Image group is not supported currently
        with pytest.raises(NotImplementedError) as e:
            next(dep_asset(self.context.image_group_storage_item))
        assert str(e.value) == DOWNLOAD_NATIVE_IMAGE_GROUP_WO_FRAME_ERROR_MESSAGE

    def test_dep_twin_label_row(
        self, context: SharedTaskDependencyResolutionContext, class_level_ephemeral_twin_project_hash: str
    ) -> None:
        # Test with valid project hash
        twin_fn = dep_twin_label_row(class_level_ephemeral_twin_project_hash)
        twin = twin_fn(context.video_label_row)
        assert isinstance(twin, Twin)
        assert isinstance(twin.label_row, LabelRowV2)
        assert twin.label_row.backing_item_uuid == context.video_label_row.backing_item_uuid

        # Test with invalid project hash
        with pytest.raises(PrintableError):
            dep_twin_label_row("invalid_project_hash")(context.video_label_row)

    def test_dep_storage_item(self, context: SharedTaskDependencyResolutionContext) -> None:
        storage_item = dep_storage_item(context.video_storage_item)
        assert isinstance(storage_item, StorageItem)
        assert storage_item.item_type == StorageItemType.VIDEO

    def test_dependency_injection_example(self, user_client: EncordUserClient) -> None:
        """Test to demonstrate how dependencies are typically used in practice"""

        def example_agent(
            client: Annotated[EncordUserClient, Depends(dep_client)],
            storage_item: Annotated[StorageItem, Depends(dep_storage_item)],
        ) -> str:
            assert isinstance(client, EncordUserClient)
            assert isinstance(storage_item, StorageItem)
            return "<pathway_uuid>"

        # The test would normally involve running this through a Runner
        # but for demonstration we just show the function signature
        assert callable(example_agent)
        storage_item = user_client.get_storage_items([self.context.video_label_row.backing_item_uuid])[0]  # type: ignore[list-item]
        assert example_agent(client=user_client, storage_item=storage_item) == "<pathway_uuid>"

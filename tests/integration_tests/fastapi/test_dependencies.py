from typing import Annotated, NamedTuple

import pytest
from encord.constants.enums import DataType
from encord.objects.coordinates import BoundingBoxCoordinates
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.ontology_object import Object
from encord.objects.ontology_object_instance import ObjectInstance
from encord.project import Project
from encord.storage import StorageItem
from encord.user_client import EncordUserClient

from encord_agents.core.data_model import FrameData, LabelRowInitialiseLabelsArgs, LabelRowMetadataIncludeArgs
from encord_agents.fastapi.cors import EncordCORSMiddleware
from encord_agents.fastapi.dependencies import (
    dep_client,
    dep_label_row,
    dep_label_row_with_args,
    dep_objects,
    dep_project,
    dep_storage_item,
)
from tests.fixtures import BBOX_ONTOLOGY_HASH, EPHEMERAL_PROJECT_TITLE

try:
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
except Exception:
    exit()


class SharedResolutionContext(NamedTuple):
    project: Project
    video_label_row: LabelRowV2
    object_hash: str


def build_app(context: SharedResolutionContext) -> FastAPI:
    project = context.project
    video_label_row = context.video_label_row
    object_hash = context.object_hash
    app = FastAPI()
    app.add_middleware(EncordCORSMiddleware)

    @app.post("/client")
    def post_client(client: Annotated[EncordUserClient, Depends(dep_client)]) -> None:
        assert isinstance(client, EncordUserClient)
        # Check we can get the right project: (Proxy for are we the right User)
        new_project = client.get_project(project_hash=project.project_hash)
        assert new_project
        assert new_project.project_hash == project.project_hash

    @app.post("/project")
    def post_project(from_dep_project: Annotated[Project, Depends(dep_project)]) -> None:
        assert from_dep_project
        assert from_dep_project.title == EPHEMERAL_PROJECT_TITLE
        assert from_dep_project.project_hash == project.project_hash

    @app.post("/label-row")
    def post_label_row(label_row: Annotated[LabelRowV2, Depends(dep_label_row)]) -> None:
        assert label_row
        assert isinstance(label_row, LabelRowV2)
        assert label_row.data_hash == video_label_row.data_hash

    @app.post("/storage-item")
    def post_storage_item(storage_item: Annotated[StorageItem, Depends(dep_storage_item)]) -> None:
        assert storage_item
        assert isinstance(storage_item, StorageItem)
        assert storage_item.uuid == video_label_row.backing_item_uuid

    include_args = LabelRowMetadataIncludeArgs(
        include_client_metadata=True,
        include_workflow_graph_node=True,
    )
    init_args = LabelRowInitialiseLabelsArgs(
        include_signed_url=True,
    )

    @app.post("/label-row-with-args")
    def post_label_row_with_args(
        label_row_with_args: Annotated[LabelRowV2, Depends(dep_label_row_with_args(include_args, init_args))],
    ) -> None:
        assert isinstance(label_row_with_args, LabelRowV2)
        assert label_row_with_args.data_hash == video_label_row.data_hash
        assert label_row_with_args.client_metadata is not None
        assert label_row_with_args.client_metadata == {"a": "b", "item_type": "video"}
        assert label_row_with_args.workflow_graph_node is not None
        assert label_row_with_args.data_link is not None

    @app.post("/frame-data-without-object-hash")
    def post_frame_data_without_object_hash(frame_data: FrameData) -> None:
        assert frame_data
        assert str(frame_data.project_hash) == project.project_hash
        assert frame_data.object_hashes is None

    @app.post("/frame-data-with-object-hash")
    def post_frame_data_with_object_hash(
        frame_data: FrameData, object_instances: Annotated[list[ObjectInstance], Depends(dep_objects)]
    ) -> None:
        assert frame_data
        assert frame_data.object_hashes == [object_hash]
        assert len(object_instances) == 1
        assert object_instances[0].object_hash == object_hash

    return app


# Load project info once for the class
@pytest.fixture(scope="class")
def context(user_client: EncordUserClient, class_level_ephemeral_project_hash: str) -> SharedResolutionContext:
    project = user_client.get_project(class_level_ephemeral_project_hash)
    label_rows = project.list_label_rows_v2()
    video_label_row = next(
        row for row in label_rows if row.data_type == DataType.VIDEO
    )  # Pick a video such that frame obviously makes sense
    video_label_row.initialise_labels()
    bbox_object = project.ontology_structure.get_child_by_hash(BBOX_ONTOLOGY_HASH, type_=Object)
    obj_instance = bbox_object.create_instance()
    obj_instance.set_for_frames(BoundingBoxCoordinates(height=0.5, width=0.5, top_left_x=0, top_left_y=0))
    video_label_row.add_object_instance(obj_instance)
    video_label_row.save()
    return SharedResolutionContext(
        project=project, video_label_row=video_label_row, object_hash=obj_instance.object_hash
    )


class TestDependencyResolutionFastapi:
    context: SharedResolutionContext
    client: TestClient

    # Set the project and first label row for the class
    @classmethod
    @pytest.fixture(autouse=True)
    def setup(cls, context: SharedResolutionContext) -> None:
        cls.context = context
        app = build_app(context)
        cls.client = TestClient(app)

    def test_client_dependency(self) -> None:
        resp = self.client.post("/client")
        assert resp.status_code == 200, resp.content

    @pytest.mark.parametrize(
        "router_path",
        [
            "/client",
            "/project",
            "/label-row",
            "/storage-item",
            "/label-row-with-args",
        ],
    )
    def test_post_dependencies(self, router_path: str) -> None:
        resp = self.client.post(
            router_path,
            json={
                "projectHash": self.context.project.project_hash,
                "dataHash": self.context.video_label_row.data_hash,
                "frame": 0,
            },
        )
        assert resp.status_code == 200, resp.content

    def test_objectHash_populated_correctly(self) -> None:
        resp = self.client.post(
            "/frame-data-without-object-hash",
            json={
                "projectHash": self.context.project.project_hash,
                "dataHash": self.context.video_label_row.data_hash,
                "frame": 0,
            },
        )
        assert resp.status_code == 200, resp.content
        resp = self.client.post(
            "/frame-data-with-object-hash",
            json={
                "projectHash": self.context.project.project_hash,
                "dataHash": self.context.video_label_row.data_hash,
                "frame": 0,
                "objectHashes": [self.context.object_hash],
            },
        )
        assert resp.status_code == 200, resp.content

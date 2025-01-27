from typing import Annotated, NamedTuple

import pytest
from encord.constants.enums import DataType
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.project import Project
from encord.storage import StorageItem
from encord.user_client import EncordUserClient

from encord_agents.core.data_model import LabelRowInitialiseLabelsArgs, LabelRowMetadataIncludeArgs
from encord_agents.fastapi.dependencies import (
    dep_client,
    dep_label_row,
    dep_label_row_with_args,
    dep_project,
    dep_storage_item,
)
from tests.fixtures import EPHEMERAL_PROJECT_TITLE

try:
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
except Exception:
    exit()


def build_app(ephermeral_project: Project, video_label_row: LabelRowV2) -> FastAPI:
    app = FastAPI()

    @app.post("/client")
    def post_client(client: Annotated[EncordUserClient, Depends(dep_client)]) -> None:
        assert isinstance(client, EncordUserClient)
        # Check we can get the right project: (Proxy for are we the right User)
        new_project = client.get_project(project_hash=ephermeral_project.project_hash)
        assert new_project
        assert new_project.project_hash == ephermeral_project.project_hash

    @app.post("/project")
    def post_project(from_dep_project: Annotated[Project, Depends(dep_project)]) -> None:
        assert from_dep_project
        assert from_dep_project.title == EPHEMERAL_PROJECT_TITLE
        assert from_dep_project.project_hash == ephermeral_project.project_hash

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

    return app


class SharedResolutionContext(NamedTuple):
    project: Project
    video_label_row: LabelRowV2


# Load project info once for the class
@pytest.fixture(scope="class")
def context(user_client: EncordUserClient, class_level_ephemeral_project_hash: str) -> SharedResolutionContext:
    project = user_client.get_project(class_level_ephemeral_project_hash)
    label_rows = project.list_label_rows_v2()
    video_label_row = next(
        row for row in label_rows if row.data_type == DataType.VIDEO
    )  # Pick a video such that frame obviously makes sense
    return SharedResolutionContext(project=project, video_label_row=video_label_row)


class TestDependencyResolutionFastapi:
    project: Project
    first_label_row: LabelRowV2
    client: TestClient

    # Set the project and first label row for the class
    @classmethod
    @pytest.fixture(autouse=True)
    def setup(cls, context: SharedResolutionContext) -> None:
        cls.project = context.project
        cls.first_label_row = context.video_label_row
        app = build_app(context.project, context.video_label_row)
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
                "projectHash": self.project.project_hash,
                "dataHash": self.first_label_row.data_hash,
                "frame": 0,
            },
        )
        assert resp.status_code == 200, resp.content

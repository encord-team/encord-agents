from typing import Annotated, AsyncGenerator, Generator, NamedTuple

import pytest
from encord.constants.enums import DataType
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.project import Project
from encord.user_client import EncordUserClient
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from encord_agents.core.data_model import FrameData
from encord_agents.fastapi.cors import EncordCORSMiddleware
from encord_agents.fastapi.dependencies import dep_client, dep_label_row, dep_project

app = FastAPI()

try:
    from fastapi import Depends, FastAPI, Request, Response
    from fastapi.testclient import TestClient
except Exception:
    pass

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

app = FastAPI()
app.add_middleware(EncordCORSMiddleware)


@app.post("/client")
def post_client(client: Annotated[EncordUserClient, Depends(dep_client)]) -> None:
    assert isinstance(client, EncordUserClient)
    assert client.list_projects()
    # TODO: Check that we are the appropriate user?
    # Is there some state? Some get_user_creds endpoint?


@app.post("/project")
def post_project(project: Annotated[Project, Depends(dep_project)]) -> None:
    assert project
    print(project.title)


@app.post("/label-row")
def post_label_row(label_row: Annotated[LabelRowV2, Depends(dep_label_row)]) -> None:
    assert label_row
    assert isinstance(label_row, LabelRowV2)
    # TODO: How to get this?
    # assert label_row.data_hash ==


client = TestClient(app)


class SharedResolutionContext(NamedTuple):
    project: Project
    first_label_row: LabelRowV2


# Load project info once for the class
@pytest.fixture(scope="class")
def context(user_client: EncordUserClient, class_level_ephemeral_project_hash: str) -> SharedResolutionContext:
    project = user_client.get_project(class_level_ephemeral_project_hash)
    label_rows = project.list_label_rows_v2()
    video_label_row = next(row for row in label_rows if row.data_type == DataType.VIDEO)
    return SharedResolutionContext(project=project, first_label_row=video_label_row)


class TestDependencyResolutionFastapi:
    project: Project
    first_label_row: LabelRowV2

    # Set the project and first label row for the class
    @classmethod
    @pytest.fixture(autouse=True)
    def setup(cls, context: SharedResolutionContext) -> None:
        cls.project = context.project
        cls.first_label_row = context.first_label_row

    def test_client_dependency(self) -> None:
        resp = client.post("/client")
        assert resp.status_code == 200

    def test_dep_project(self) -> None:
        resp = client.post(
            "/project",
            json={
                "projectHash": self.project.project_hash,
                "dataHash": self.first_label_row.data_hash,
                "frame": 0,
            },
        )
        assert resp.status_code == 200, resp.content

    def test_dep_label_row(self) -> None:
        resp = client.post(
            "/label-row",
            headers={"Content-Type": "application/json"},
            json={
                "projectHash": self.project.project_hash,
                "dataHash": self.first_label_row.data_hash,
                "frame": 0,
            },
        )
        assert resp.status_code == 200

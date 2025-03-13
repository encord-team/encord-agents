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


def test_auth_router(
    ephermeral_project_hash: str,
    authenticated_user_token: str,
    unauthenticated_user_token: str,
) -> None:
    app = FastAPI()
    # app.add_middleware(EncordAuthMiddleware)

    @app.post("/client")
    def client(client: Annotated[EncordUserClient, Depends(dep_client)]) -> None:
        assert client
        client.get_project(ephermeral_project_hash)

    test_client = TestClient(app)

    resp = test_client.post("/client", headers={"Authorization": f"Bearer {authenticated_user_token}"})
    assert resp.status_code == 200

    resp = test_client.post("/client", headers={"Authorization": f"Bearer {unauthenticated_user_token}"})
    assert resp.status_code == 403

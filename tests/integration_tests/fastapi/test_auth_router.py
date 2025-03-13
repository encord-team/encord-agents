from typing import Annotated

from encord.exceptions import AuthorisationError
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.user_client import EncordUserClient
from fastapi import HTTPException

from encord_agents.core.utils import get_user_client_from_token
from encord_agents.fastapi.cors import EncordCORSMiddleware
from encord_agents.fastapi.dependencies import (
    dep_client,
    dep_label_row,
)

try:
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
except Exception:
    exit()


def test_auth_router(
    ephemeral_project_hash: str,
    authenticated_user_token: str,
    unauthenticated_user_token: str,
) -> None:
    app = FastAPI()
    # app.add_middleware(EncordAuthMiddleware)

    @app.post("/client")
    def client(client: Annotated[EncordUserClient, Depends(dep_client)]) -> None:
        assert client
        try:
            client.get_project(ephemeral_project_hash)
        except AuthorisationError:
            raise HTTPException(status_code=403)

    test_client = TestClient(app)

    resp = test_client.post("/client", headers={"Authorization": f"Bearer {authenticated_user_token}"})
    assert resp.status_code == 200

    resp = test_client.post("/client", headers={"Authorization": f"Bearer {unauthenticated_user_token}"})
    assert resp.status_code == 403, resp.content


# TODO: Need a body to test against see FastAPI example
def test_auth_router_label_row(
    ephemeral_project_hash: str,
    authenticated_user_token: str,
    unauthenticated_user_token: str,
) -> None:
    app = FastAPI()
    app.add_middleware(EncordCORSMiddleware)

    @app.post("/label_row")
    def client(label_row: Annotated[LabelRowV2, Depends(dep_label_row)]) -> None:
        assert label_row

    test_client = TestClient(app)
    user_client = get_user_client_from_token(authenticated_user_token)
    project = user_client.get_project(ephemeral_project_hash)
    lr = project.list_label_rows_v2()[0]
    data_hash = lr.data_hash

    payload: dict[str, str | int] = {
        "projectHash": ephemeral_project_hash,
        "dataHash": data_hash,
        "frame": 0,
    }

    resp = test_client.post(
        "/label_row",
        headers={"Authorization": f"Bearer {authenticated_user_token}"},
        json=payload,
    )
    assert resp.status_code == 200, resp.content

    resp = test_client.post(
        "/label_row",
        headers={"Authorization": f"Bearer {unauthenticated_user_token}"},
        json=payload,
    )
    assert resp.status_code == 403, resp.content

from typing import Annotated

from encord.objects.ontology_labels_impl import LabelRowV2

from encord_agents.core.constants import TEST_REQUEST_HEADER
from encord_agents.core.data_model import FrameData
from encord_agents.fastapi.cors import EncordCORSMiddleware
from encord_agents.fastapi.dependencies import (
    dep_label_row,
)

try:
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
except Exception:
    exit()


def test_fastapi_can_handle_placeholder_payload() -> None:
    app = FastAPI()
    app.add_middleware(EncordCORSMiddleware)
    counter = 0

    @app.post("/test")
    def frame_data(
        frame_data: FrameData,
        label_row: Annotated[LabelRowV2, Depends(dep_label_row)],
    ) -> None:
        nonlocal counter
        counter += 1

    client = TestClient(app)
    resp = client.post(
        "/test",
        headers={TEST_REQUEST_HEADER: "test-content"},
        json={
            "projectHash": "00000000-0000-0000-0000-000000000000",
            "dataHash": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "frame": 10,
        },
    )
    assert resp.status_code == 200, resp.content
    assert counter == 0

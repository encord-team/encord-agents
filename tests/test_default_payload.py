from typing import Annotated

from encord.objects.ontology_labels_impl import LabelRowV2

from encord_agents.core.constants import EDITOR_TEST_REQUEST_HEADER
from encord_agents.core.data_model import FrameData
from encord_agents.fastapi.cors import get_encord_app
from encord_agents.fastapi.dependencies import (
    dep_label_row,
)

try:
    from fastapi import Depends
    from fastapi.testclient import TestClient
except Exception:
    exit()


def test_fastapi_can_handle_placeholder_payload() -> None:
    app = get_encord_app()
    counter = 0

    @app.post("/test")
    def frame_data(
        frame_data: FrameData,
        label_row: Annotated[LabelRowV2, Depends(dep_label_row)],
    ) -> None:
        nonlocal counter
        counter += 1

    client = TestClient(app)
    options_resp = client.options(
        "/test",
        headers={
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": EDITOR_TEST_REQUEST_HEADER,
            "Origin": "https://app.encord.com",
        },
    )
    assert options_resp.status_code == 200, options_resp.content
    assert "Access-Control-Allow-Origin" in options_resp.headers
    assert "Access-Control-Allow-Headers" in options_resp.headers
    assert EDITOR_TEST_REQUEST_HEADER in options_resp.headers["Access-Control-Allow-Headers"]

    resp = client.post(
        "/test",
        headers={EDITOR_TEST_REQUEST_HEADER: "test-content"},
        json={
            "projectHash": "00000000-0000-0000-0000-000000000000",
            "dataHash": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "frame": 10,
        },
    )
    assert resp.status_code == 200, resp.content
    assert counter == 0

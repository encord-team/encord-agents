from typing import Annotated

from encord.user_client import EncordUserClient
from fastapi import Depends
from fastapi.testclient import TestClient

from encord_agents.fastapi.cors import get_encord_app
from encord_agents.fastapi.dependencies import dep_client
from tests.fixtures import ENCORD_ORIGIN


class TestCustomCorsRegex:
    def test_custom_cors_regex(self) -> None:
        app = get_encord_app(custom_cors_regex="https://example.com")

        @app.post("/client")
        def post_client(client: Annotated[EncordUserClient, Depends(dep_client)]) -> None:
            assert isinstance(client, EncordUserClient)

        client = TestClient(app)
        # Verify preflight response
        preflight_headers = {
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,Authorization",
        }

        preflight_response = client.options("/your-endpoint", headers=preflight_headers)
        assert preflight_response.status_code == 200
        assert preflight_response.headers["Access-Control-Allow-Origin"] == "https://example.com"
        assert "POST" in preflight_response.headers["Access-Control-Allow-Methods"]
        assert "Content-Type" in preflight_response.headers["Access-Control-Allow-Headers"]
        assert "Authorization" in preflight_response.headers["Access-Control-Allow-Headers"]
        resp = client.post("/client", headers={"Origin": "https://example.com"})
        assert resp.status_code == 200, resp.content
        assert resp.headers["Access-Control-Allow-Origin"] == "https://example.com"

        resp = client.post("/client", headers={"Origin": "https://not-example.com"})
        assert resp.status_code == 200, resp.content
        assert "Access-Control-Allow-Origin" not in resp.headers

    def test_custom_cors_regex_with_none(self) -> None:
        app = get_encord_app(custom_cors_regex=None)

        @app.post("/client")
        def post_client(client: Annotated[EncordUserClient, Depends(dep_client)]) -> None:
            assert isinstance(client, EncordUserClient)

        client = TestClient(app)
        resp = client.post("/client", headers={"Origin": ENCORD_ORIGIN})
        assert resp.status_code == 200, resp.content
        assert resp.headers["Access-Control-Allow-Origin"] == ENCORD_ORIGIN

        resp = client.post("/client", headers={"Origin": "https://example.com"})
        assert resp.status_code == 200, resp.content
        assert "Access-Control-Allow-Origin" not in resp.headers

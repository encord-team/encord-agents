from typing import Annotated

from encord.user_client import EncordUserClient
from fastapi import Depends
from fastapi.testclient import TestClient

from encord_agents.fastapi.cors import get_encord_app
from encord_agents.fastapi.dependencies import dep_client


class TestCustomCorsRegex:
    def test_custom_cors_regex(self) -> None:
        app = get_encord_app(custom_cors_regex="https://example.com")

        @app.post("/client")
        def post_client(client: Annotated[EncordUserClient, Depends(dep_client)]) -> None:
            assert isinstance(client, EncordUserClient)

        client = TestClient(app)
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
        resp = client.post("/client", headers={"Origin": "https://app.encord.com"})
        assert resp.status_code == 200, resp.content
        assert resp.headers["Access-Control-Allow-Origin"] == "https://app.encord.com"

        resp = client.post("/client", headers={"Origin": "https://example.com"})
        assert resp.status_code == 200, resp.content
        assert "Access-Control-Allow-Origin" not in resp.headers

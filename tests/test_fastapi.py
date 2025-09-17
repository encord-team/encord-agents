import re
from typing import Annotated
from unittest.mock import MagicMock, patch

from encord.user_client import EncordUserClient
from fastapi import Depends
from fastapi.testclient import TestClient
from requests import Session

from encord_agents.core.constants import HEADER_CLOUD_TRACE_CONTEXT
from encord_agents.core.exceptions import EncordEditorAgentException
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

        @app.post("/client-throws")
        def post_client_throws(client: Annotated[EncordUserClient, Depends(dep_client)]) -> None:
            raise EncordEditorAgentException(message="Error message")

        client = TestClient(app)
        resp = client.post("/client", headers={"Origin": "https://app.encord.com"})
        assert resp.status_code == 200, resp.content
        assert resp.headers["Access-Control-Allow-Origin"] == "https://app.encord.com"

        resp = client.post("/client", headers={"Origin": "https://example.com"})
        assert resp.status_code == 200, resp.content
        assert "Access-Control-Allow-Origin" not in resp.headers

        # Check that even when we are returning a non 200, we have the appropriate headers on the response
        resp = client.post("/client-throws", headers={"Origin": "https://app.encord.com"})
        assert resp.status_code == 400, resp.content
        assert resp.headers["Access-Control-Allow-Origin"] == "https://app.encord.com"

    def test_trace_id_used_appropriately(
        self,
    ) -> None:
        app = get_encord_app()

        trace_id = "a7b2e5f5ff29466fa0a787cf931106a9"

        CLOUD_TRACE_CONTEXT_RE = re.compile(
            r"^(?P<trace_id>[0-9a-f]{32})/(?P<span_id>[0-9]{1,20});o=(?P<options>[01])$"
        )

        state = iter([1, 2])

        def fake_randbits(_: int) -> int:
            nonlocal state
            return next(state)

        @app.post("/client")
        def post_client(client: Annotated[EncordUserClient, Depends(dep_client)]) -> None:
            assert isinstance(client, EncordUserClient)
            with patch.object(Session, "send") as send:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = None
                mock_response.content = "null"
                send.return_value = mock_response
                with patch("encord_agents.core.utils.random.getrandbits", side_effect=fake_randbits) as rand_seed:
                    client._api_client.post("/", params=None, payload=None, result_type=None)
                    send.assert_called_once()
                    rand_seed.assert_called_once()
                    req = send.call_args.args[0]
                    assert req.headers.get(HEADER_CLOUD_TRACE_CONTEXT) == f"{trace_id}/1;o=1"
                    client._api_client.post("/", params=None, payload=None, result_type=None)
                    assert rand_seed.call_count == 2
                    req = send.call_args.args[0]
                    assert req.headers.get(HEADER_CLOUD_TRACE_CONTEXT) == f"{trace_id}/2;o=1"

                # Check for unpatched randomness matches regex
                client._api_client.post("/", params=None, payload=None, result_type=None)
                req = send.call_args.args[0]
                x_cloud_trace_context = req.headers.get(HEADER_CLOUD_TRACE_CONTEXT)
                assert CLOUD_TRACE_CONTEXT_RE.match(x_cloud_trace_context)

        client = TestClient(app)
        resp = client.post(
            "/client", headers={"Origin": "https://app.encord.com", HEADER_CLOUD_TRACE_CONTEXT: f"{trace_id}/1;o=1"}
        )
        assert resp.status_code == 200

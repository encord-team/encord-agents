"""Serialisation contract for `EditorAgentResponse` across the serverless wrappers.

Encord reads `decision` and `message` off the JSON body of a 2xx agent response, so
these tests assert the wire shape each wrapper produces, not just that it returned.
"""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, Request
from pydantic import ValidationError
from werkzeug.test import EnvironBuilder

from encord_agents.aws.wrappers import editor_agent as aws_editor_agent
from encord_agents.core.data_model import EditorAgentResponse, FrameData
from encord_agents.gcp.wrappers import editor_agent as gcp_editor_agent

PAYLOAD = {
    "projectHash": "00000000-0000-0000-0000-000000000000",
    "dataHash": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "frame": 0,
}


def test_decision_strips_and_treats_blank_as_unset() -> None:
    assert EditorAgentResponse(decision="  accept  ").decision == "accept"
    assert EditorAgentResponse(decision="   ").decision is None
    assert EditorAgentResponse(decision="").decision is None
    assert EditorAgentResponse(message="\t\n").message is None


def test_decision_longer_than_the_platform_cap_is_rejected() -> None:
    # Encord silently ignores an over-long decision and routes via the default pathway,
    # so failing loudly here is the difference between an error and a wrong pathway.
    with pytest.raises(ValidationError):
        EditorAgentResponse(decision="x" * 257)

    assert EditorAgentResponse(decision="x" * 256).decision is not None


def _gcp_response_body(response: EditorAgentResponse) -> dict[str, Any]:
    @gcp_editor_agent()
    def agent(frame_data: FrameData) -> EditorAgentResponse:
        return response

    request = Request(EnvironBuilder(method="POST", json=PAYLOAD).get_environ())
    with patch("encord_agents.gcp.wrappers.get_user_client", return_value=MagicMock()):
        # `make_response` needs an application context; the request above is what the
        # wrapper actually reads.
        with Flask(__name__).test_request_context():
            flask_response = agent(request)
    assert flask_response.status_code == 200
    body: dict[str, Any] = json.loads(flask_response.get_data(as_text=True))
    return body


def _aws_response(response: EditorAgentResponse) -> dict[str, Any]:
    @aws_editor_agent()
    def agent(frame_data: FrameData) -> EditorAgentResponse:
        return response

    with patch("encord_agents.aws.wrappers.get_user_client", return_value=MagicMock()):
        return agent({"headers": {}, "body": json.dumps(PAYLOAD)}, None)


def test_gcp_serializes_decision_and_omits_unset_fields() -> None:
    body = _gcp_response_body(EditorAgentResponse(decision="accept"))
    assert body == {"decision": "accept"}

    body = _gcp_response_body(EditorAgentResponse(decision="reject", message="Two boxes out of bounds"))
    assert body == {"decision": "reject", "message": "Two boxes out of bounds"}


def test_aws_body_is_a_json_string() -> None:
    # API Gateway discards a proxy response whose body is not a string, which would
    # drop the decision on the floor without any error surfacing.
    aws_response = _aws_response(EditorAgentResponse(decision="accept"))
    assert isinstance(aws_response["body"], str)
    assert json.loads(aws_response["body"]) == {"decision": "accept"}


def test_aws_error_bodies_are_json_strings() -> None:
    @aws_editor_agent()
    def agent(frame_data: FrameData) -> None:
        return None

    missing_body = agent({"headers": {}}, None)
    assert missing_body["statusCode"] == 400
    assert isinstance(missing_body["body"], str)
    assert json.loads(missing_body["body"])["message"] == "No request body"

    malformed = agent({"headers": {}, "body": json.dumps({"frame": -1})}, None)
    assert malformed["statusCode"] == 400
    assert isinstance(malformed["body"], str)
    assert json.loads(malformed["body"])["errors"]

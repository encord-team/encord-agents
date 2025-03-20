import os
from contextlib import nullcontext

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import encord_agents
from encord_agents.cli.test import parse_editor_url
from encord_agents.core.utils import get_user_client

PRIVATE_KEY = Ed25519PrivateKey.generate()


PRIVATE_KEY_PEM = PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.OpenSSH,
    encryption_algorithm=serialization.NoEncryption(),
).decode("utf-8")


@pytest.mark.skipif(encord_agents.__version__ <= "v0.1.5", reason="Underlying Encord dependency not yet bumped")
def test_user_agent_defined_appropriately() -> None:
    os.environ["ENCORD_SSH_KEY"] = PRIVATE_KEY_PEM
    user_client = get_user_client()

    assert "encord-agents" in user_client._api_client._config._user_agent()


@pytest.mark.parametrize(
    "editor_url, is_ok",
    [
        pytest.param(
            "https://app.encord.com/label_editor/e262cefc-cb58-4722-82dd-01033dd1682a/1704cae4-aced-4141-ba34-216698f16520/0/0/",
            True,
            id="Basic with additional /0 suffix",
        ),
        pytest.param(
            "https://app.us.encord.com/label_editor/e262cefc-cb58-4722-82dd-01033dd1682a/1704cae4-aced-4141-ba34-216698f16520/0/0/",
            True,
            id="US with additional /0 suffix",
        ),
        pytest.param(
            "https://app.us.encord.com/label_editor/e262cefc-cb58-4722-82dd-01033dd1682a/1704cae4-aced-4141-ba34-216698f16520/0/",
            True,
            id="US",
        ),
        pytest.param(
            "https://app.encord.com/label_editor/7269079d-7c0f-484e-9199-2ab498dd70ac/172d82f2-c942-4fe4-b498-829dc1085b32/0/1?selectedStageUuid=8cac6636-2ef1-4bbe-848a-b5ffee158c34&reviewId=57e8651d-7f13-49df-accb-67f0789d62d7",
            True,
            id="Non US With full URL",
        ),
        pytest.param(
            "https://app.encord.com/label_editor/0d5d1d19-4e75-4fa3-8b87-f6311d4c3f50/a8afe7bd-2847-43f8-91df-41ca787e7bcb/0/",
            True,
            id="US no suffix",
        ),
        pytest.param("http://encord.com", False, id="Top level encord domain"),
        pytest.param("http://app.encord.com", False, id="Top level encord app"),
        pytest.param("http://app.encord.com/label_editor/", False, id="label editor no params"),
        pytest.param(
            "https://app.encord.com/label_editor/fc9e493c-6a01-4c67-b91a-cce050aad76e/18b1327a-c4de-4aa3-b87a-23134a158169?selectedStageUuid=a1063abb-501e-42e3-9008-f8b5204e6eaf&agentTaskId=014ec4e2-3e5e-466e-9fda-3f0ecdcab3b2",
            True,
            id="Agent task. No frame",
        ),
        pytest.param(
            "https://app.encord.com/label_editor/14946df6-4137-4cf7-8a50-b64a8345b8bd/0df67392-cbae-48f8-a914-26d8127ecaa5/0/1?selectedStageUuid=8cac6636-2ef1-4bbe-848a-b5ffee158c34&reviewId=1402cbad-f5a5-47d7-a957-3952403c8b33",
            True,
            id="Agent task frame",
        ),
        pytest.param(
            "https://app.encord.com/label_editor/14946df6-4137-4cf7-8a50-b64a8345b8bd/0df67392-cbae-48f8-a914-26d8127ecaa5/",
            True,
            id="Basic with no frame",
        ),
        pytest.param(
            "https://app.encord.com/label_editor/153bccb3-2c74-4482-95ef-48a15108b6ba/0403eaa5-3b69-4c2a-92c2-4a8e31af02ef/0/0?selectedStageUuid=1252fdb8-93cb-41a2-b341-b83ab97b5277&taskId=b0eb2e18-217a-4273-8faf-5ec55c1b7aa1&objectHash=KcXM2H8t",
            True,
            id="Long form with object hash",
        ),
    ],
)
def test_editor_url_regex(editor_url: str, is_ok: bool) -> None:
    context = nullcontext() if is_ok else pytest.raises(Exception)
    with context:
        frame_data, domain = parse_editor_url(editor_url)
    if is_ok:
        assert frame_data
        assert domain


def test_editor_url_regex_object_hash() -> None:
    frame_data, domain = parse_editor_url(
        "https://app.encord.com/label_editor/153bccb3-2c74-4482-95ef-48a15108b6ba/0403eaa5-3b69-4c2a-92c2-4a8e31af02ef/0/0?selectedStageUuid=1252fdb8-93cb-41a2-b341-b83ab97b5277&taskId=b0eb2e18-217a-4273-8faf-5ec55c1b7aa1&objectHash=KcXM2H8t"
    )
    assert frame_data.object_hashes
    assert frame_data.object_hashes == ["KcXM2H8t"]

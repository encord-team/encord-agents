import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import encord_agents
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

    assert "encord-agent" in user_client._api_client._config._user_agent()

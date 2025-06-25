import os
from collections.abc import Iterator
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Generator
from unittest.mock import MagicMock

import pytest
from encord.dataset import Dataset
from encord.ontology import Ontology
from encord.project import Project
from encord.user_client import EncordUserClient

ONTOLOGY_HASH = "6d8bb167-0c9d-43b1-a577-3da0693d664e"
ONE_OF_EACH_DATASET_HASH = (
    # dataset with [image, image group, image_sequence, pdf, audio, txt, data_group (Audio, Text) and video]
    "5d06b07b-135a-4c6d-ba5d-fa7048d996da"
)
IMAGES_520_DATASET_HASH = (
    # dataset with 520 small images
    "d0370f27-da4c-48fa-8502-049b55e26a5f"
)
# Client metadata of the form: {"item_type": item.item_type, "a": "b"}

# Workflow:
AGENT_TO_COMPLETE_WORKFLOW_HASH = "a59b3190-09e2-432c-a8bb-f2925872e298"

AGENT_STAGE_NAME = "Agent 1"
COMPLETE_STAGE_NAME = "Complete"
AGENT_TO_COMPLETE_PATHWAY_HASH = "49a786f3-5edf-4b94-aff0-3da9042d3bf0"
AGENT_TO_COMPLETE_PATHWAY_NAME = "complete"

EPHEMERAL_PROJECT_TITLE = "encord-agents test project"
EPHEMERAL_PROJECT_DESCRIPTION = "encord-agents test project description"

# Ontology
BBOX_ONTOLOGY_HASH = "PXFZO2ra"
"""
=== HACK being ===
Hack to enable the tests to run with the key file as well as the key content.

Tests expect  (the invariant)
os.environ["ENCORD_SSH_KEY"] to be set.
os.environ["ENCORD_SSH_KEY_FILE"] to not be set.

If key file is set, read the file content over to the content env variable, 
and remove the file env variable.
"""
key_file_path = os.environ.get("ENCORD_SSH_KEY_FILE")
if os.environ.get("ENCORD_SSH_KEY") is None:
    if key_file_path is not None:
        key_content = Path(key_file_path).read_text()
        os.environ["ENCORD_SSH_KEY"] = key_content
    else:
        raise ValueError("Neither ENCORD_SSH_KEY nor ENCORD_SSH_KEY_FILE is set.")
if key_file_path is not None:
    del os.environ["ENCORD_SSH_KEY_FILE"]
"""
=== HACK end ===
"""


@pytest.fixture(scope="session")
def os_env_key_file() -> Generator[Path, None, None]:
    key_content = os.environ["ENCORD_SSH_KEY"]
    with NamedTemporaryFile(mode="w", suffix=".key", delete=False) as f:
        f.write(key_content)
        temp_path = Path(f.name)
    try:
        yield temp_path
    finally:
        temp_path.unlink(missing_ok=True)


@pytest.fixture(scope="module")
def user_client() -> EncordUserClient:
    """
    Note: No test for custom domains yet.
    """
    return EncordUserClient.create_with_ssh_private_key()


@pytest.fixture(scope="module")
def all_purpose_ontology(user_client: EncordUserClient) -> Generator[Ontology, None, None]:
    yield user_client.get_ontology(ONTOLOGY_HASH)


@pytest.fixture(scope="module")
def dataset(
    user_client: EncordUserClient,
) -> Dataset:
    return user_client.get_dataset(ONE_OF_EACH_DATASET_HASH)


@pytest.fixture(scope="module")
def workflow_hash(
    user_client: EncordUserClient,
) -> str:
    """
    Workflow:
        Template hash: "a59b3190-09e2-432c-a8bb-f2925872e298"

            Uuid: "6011c844-fb26-438b-b465-0b0825951015"
                        │
                        │ Uuid: "7e7598de-612c-40c4-ba08-5dfec8c3ae8f"
                        │                 │
    ┌─────────┐    ┌─────┴─────┐    ┌──────┴─────┐
    │  start  ├───►│  Agent 1  ├─┬─►│  Complete  │
    └─────────┘    └───────────┘ │  └────────────┘
                                │
                            Name: "complete"
                            Uuid: "49a786f3-5edf-4b94-aff0-3da9042d3bf0"
    """
    return AGENT_TO_COMPLETE_WORKFLOW_HASH


def create_default_project(
    user_client: EncordUserClient,
    all_purpose_ontology: Ontology,
    workflow_hash: str,
    dataset_hash: str,
) -> Iterator[str]:
    project_hash = user_client.create_project(
        project_title=EPHEMERAL_PROJECT_TITLE,
        dataset_hashes=[dataset_hash],
        project_description=EPHEMERAL_PROJECT_DESCRIPTION,
        ontology_hash=all_purpose_ontology.ontology_hash,
        workflow_template_hash=workflow_hash,
    )
    yield project_hash
    user_client.querier.basic_delete(Project, uid=project_hash)


def ephemeral_project_hash_base(
    user_client: EncordUserClient,
    all_purpose_ontology: Ontology,
    workflow_hash: str,
    dataset_hash: str,
) -> Iterator[str]:
    print(f"Creating ephemeral project hash Default: {dataset_hash==ONE_OF_EACH_DATASET_HASH}")
    yield from create_default_project(user_client, all_purpose_ontology, workflow_hash, dataset_hash)


@pytest.fixture(scope="function")
def ephemeral_project_hash(
    user_client: EncordUserClient,
    all_purpose_ontology: Ontology,
    workflow_hash: str,
) -> Iterator[str]:
    yield from ephemeral_project_hash_base(user_client, all_purpose_ontology, workflow_hash, ONE_OF_EACH_DATASET_HASH)


@pytest.fixture(scope="function")
def ephemeral_image_project_hash(
    user_client: EncordUserClient,
    all_purpose_ontology: Ontology,
    workflow_hash: str,
) -> Iterator[str]:
    yield from ephemeral_project_hash_base(user_client, all_purpose_ontology, workflow_hash, IMAGES_520_DATASET_HASH)


@pytest.fixture(scope="class")
def class_level_ephemeral_project_hash(
    user_client: EncordUserClient,
    all_purpose_ontology: Ontology,
    workflow_hash: str,
) -> Iterator[str]:
    yield from create_default_project(user_client, all_purpose_ontology, workflow_hash, ONE_OF_EACH_DATASET_HASH)


@pytest.fixture(scope="class")
def class_level_ephemeral_twin_project_hash(
    user_client: EncordUserClient,
    all_purpose_ontology: Ontology,
    workflow_hash: str,
) -> Iterator[str]:
    yield from create_default_project(user_client, all_purpose_ontology, workflow_hash, ONE_OF_EACH_DATASET_HASH)


@pytest.fixture(scope="function")
def mock_agent() -> MagicMock:
    return MagicMock(return_value=AGENT_TO_COMPLETE_PATHWAY_NAME)

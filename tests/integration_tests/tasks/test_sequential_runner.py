from unittest.mock import MagicMock

import pytest
from encord.user_client import EncordUserClient
from encord.workflow.stages.agent import AgentTask

from encord_agents.core.utils import batch_iterator
from encord_agents.tasks import Runner
from tests.fixtures import IMAGES_520_DATASET_HASH, ONE_OF_EACH_DATASET_HASH


@pytest.fixture
def mock_agent() -> MagicMock:
    return MagicMock(return_value="complete")


@pytest.fixture
def project_hash(request: pytest.FixtureRequest, ephemeral_project_hash: str, ephemeral_image_project_hash: str) -> str:
    """Fixture that returns either ephemeral_project_hash or ephemeral_image_project_hash based on the parameter"""
    if request.param == "ephemeral_project_hash":
        return ephemeral_project_hash
    elif request.param == "ephemeral_image_project_hash":
        return ephemeral_image_project_hash
    raise ValueError(f"Unknown project hash type: {request.param}")


def test_batch_iterator() -> None:
    batch_size = 10
    tasks = [f"hash_{i:02d}" for i in range(99)]
    batches = list(batch_iterator(tasks, batch_size))
    assert len(batches) == 10
    assert all([len(batch) == batch_size for batch in batches[:-1]])
    assert len(batches[-1]) == 9

    # Test the content of the batches
    for i, batch in enumerate(batches):
        for j, s in enumerate(batch):
            assert s == f"hash_{i * batch_size + j:02d}"


@pytest.mark.parametrize(
    "project_hash",
    [
        pytest.param("ephemeral_project_hash", id="test_runner_stage_execution_count_project"),
        pytest.param("ephemeral_image_project_hash", id="test_runner_stage_execution_count_image_project"),
    ],
    indirect=True,
)
def test_runner_stage_execution_count(user_client: EncordUserClient, mock_agent: MagicMock, project_hash: str) -> None:
    """Test that runner stage functions are called once for each task in the stage"""
    # Create runner instance
    print(f"project_hash: {project_hash}")
    runner = Runner(project_hash=project_hash)

    # Register the mock function as a stage handler
    @runner.stage("Agent 1")
    def agent_function(task: AgentTask) -> str:
        mock_agent(task)
        return "complete"

    # Run the runner
    runner(task_batch_size=11)  # 520 tasks / 11 = 47 full batches + 3 tasks in the last batch

    # Get the project to check number of tasks
    project = runner.project
    assert project

    complete_stage = next(s for s in project.workflow.stages if s.title == "Complete")
    tasks = list(complete_stage.get_tasks())

    dataset_info = list(project.list_datasets())[0]
    dataset = user_client.get_dataset(dataset_info.dataset_hash)

    # Verify the mock was called exactly once for each task
    assert mock_agent.call_count == len(tasks) and mock_agent.call_count == len(
        dataset.data_rows
    ), f"Agent function should be called {len(tasks)} times, but was called {mock_agent.call_count} times"


def test_runner_stage_execution_with_max_tasks(ephemeral_image_project_hash: str, mock_agent: MagicMock) -> None:
    """Test that runner respects max_tasks_per_stage parameter"""
    runner = Runner(project_hash=ephemeral_image_project_hash)

    @runner.stage("Agent 1")
    def agent_function(task: AgentTask) -> str:
        mock_agent(task)
        return "complete"

    # Run with max_tasks_per_stage=2
    max_tasks = 2
    runner(max_tasks_per_stage=max_tasks)

    # Verify the mock was called exactly max_tasks times
    assert (
        mock_agent.call_count == max_tasks
    ), f"Agent function should be called {max_tasks} times, but was called {mock_agent.call_count} times"


def test_runner_stage_execution_without_pathway(ephemeral_project_hash: str, mock_agent: MagicMock) -> None:
    """Test that runner handles None return value from stage function"""
    runner = Runner(project_hash=ephemeral_project_hash)

    mock_agent.return_value = None

    @runner.stage("Agent 1")
    def agent_function(task: AgentTask) -> None:
        mock_agent(task)
        return None

    # Run the runner
    runner()

    # Add null check for runner.project to satisfy mypy
    assert runner.project is not None, "Project should not be None at this point"

    agent_stage = next(s for s in runner.project.workflow.stages if s.title == "Agent 1")
    num_tasks_left_in_agent_stage = len(list(agent_stage.get_tasks()))
    num_tasks_in_the_project = len(list(runner.project.list_label_rows_v2()))

    # Verify the mock was called at least once
    assert num_tasks_left_in_agent_stage == num_tasks_in_the_project, "Agent function should be called at least once"

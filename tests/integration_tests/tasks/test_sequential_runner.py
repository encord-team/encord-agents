from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.storage import StorageItem
from encord.user_client import EncordUserClient
from encord.workflow.stages.agent import AgentStage, AgentTask
from encord.workflow.stages.final import FinalStage

from encord_agents.core.utils import batch_iterator
from encord_agents.exceptions import PrintableError
from encord_agents.tasks import Runner
from tests.fixtures import (
    AGENT_STAGE_NAME,
    AGENT_TO_COMPLETE_PATHWAY_HASH,
    AGENT_TO_COMPLETE_PATHWAY_NAME,
    COMPLETE_STAGE_NAME,
)


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


def test_define_agent(ephemeral_project_hash: str) -> None:
    runner = Runner(project_hash=ephemeral_project_hash)

    @runner.stage(AGENT_STAGE_NAME)
    def agent_func() -> None:
        return None

    with pytest.raises(PrintableError):

        @runner.stage(COMPLETE_STAGE_NAME)
        def complete_func() -> None:
            return None


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
    @runner.stage(AGENT_STAGE_NAME)
    def agent_function(task: AgentTask) -> str:
        mock_agent(task)
        return AGENT_TO_COMPLETE_PATHWAY_NAME

    # Get the project to check number of tasks
    project = runner.project
    assert project
    N_items = len(project.list_label_rows_v2())
    agent_stage = project.workflow.get_stage(name=AGENT_STAGE_NAME, type_=AgentStage)
    agent_stage_tasks = list(agent_stage.get_tasks())
    assert N_items == len(agent_stage_tasks)
    # Run the runner
    runner(task_batch_size=11)  # 520 tasks / 11 = 47 full batches + 3 tasks in the last batch

    complete_stage = project.workflow.get_stage(name=COMPLETE_STAGE_NAME, type_=FinalStage)
    complete_stage_tasks = list(complete_stage.get_tasks())

    # Verify the mock was called exactly once for each task

    assert mock_agent.call_count == N_items
    assert len(complete_stage_tasks) == N_items

    # Check that we have no tasks at Agent stage and haven't made tasks somehow
    agent_stage = project.workflow.get_stage(name=AGENT_STAGE_NAME, type_=AgentStage)
    agent_stage_tasks = list(agent_stage.get_tasks())
    assert len(agent_stage_tasks) == 0


def test_runner_stage_execution_with_max_tasks(ephemeral_image_project_hash: str, mock_agent: MagicMock) -> None:
    """Test that runner respects max_tasks_per_stage parameter"""
    runner = Runner(project_hash=ephemeral_image_project_hash)

    @runner.stage(AGENT_STAGE_NAME)
    def agent_function(task: AgentTask) -> str:
        mock_agent(task)
        return AGENT_TO_COMPLETE_PATHWAY_NAME

    # Run with max_tasks_per_stage=2
    max_tasks = 2
    runner(max_tasks_per_stage=max_tasks)

    # Verify the mock was called exactly max_tasks times
    assert (
        mock_agent.call_count == max_tasks
    ), f"Agent function should be called {max_tasks} times, but was called {mock_agent.call_count} times"

    # Check that we've moved 2 and only 2 tasks
    project = runner.project
    assert project
    N_items = len(project.list_label_rows_v2())
    complete_stage = project.workflow.get_stage(name=COMPLETE_STAGE_NAME, type_=FinalStage)
    assert len(list(complete_stage.get_tasks())) == 2

    agent_stage = project.workflow.get_stage(name=AGENT_STAGE_NAME, type_=AgentStage)
    agent_stage_tasks = list(agent_stage.get_tasks())
    assert len(agent_stage_tasks) == N_items - 2


def test_runner_stage_execution_without_pathway(ephemeral_project_hash: str, mock_agent: MagicMock) -> None:
    """Test that runner handles None return value from stage function"""
    runner = Runner(project_hash=ephemeral_project_hash)

    mock_agent.return_value = None

    @runner.stage(AGENT_STAGE_NAME)
    def agent_function(task: AgentTask) -> None:
        mock_agent(task)
        return None

    # Run the runner
    runner()

    # Add null check for runner.project to satisfy mypy
    assert runner.project is not None, "Project should not be None at this point"

    agent_stage = next(s for s in runner.project.workflow.stages if s.title == AGENT_STAGE_NAME)
    num_tasks_left_in_agent_stage = len(list(agent_stage.get_tasks()))
    num_tasks_in_the_project = len(list(runner.project.list_label_rows_v2()))

    # Verify that we haven't moved any tasks
    assert num_tasks_left_in_agent_stage == num_tasks_in_the_project, "Should still be N tasks at the Agent stage"
    # Verify the mock was called at least once
    assert mock_agent.call_count == num_tasks_in_the_project


@pytest.mark.parametrize(
    "provide_project_hash_at_define_time",
    [
        True,
        False,
    ],
)
def test_project_validation_callback_trivial(
    ephemeral_project_hash: str, provide_project_hash_at_define_time: bool
) -> None:
    validation_mock = MagicMock()
    validation_mock.return_value = None

    runner = Runner(
        project_hash=ephemeral_project_hash if provide_project_hash_at_define_time else None,
        pre_execution_callback=validation_mock,
    )
    # Check not validated at define time
    validation_mock.assert_not_called()

    @runner.stage(AGENT_STAGE_NAME)
    def stage_1() -> None:
        return None

    runner(
        project_hash=ephemeral_project_hash if not provide_project_hash_at_define_time else None,
    )
    # Check validated at run time
    validation_mock.assert_called_once_with(runner)


def test_project_validation_callback_non_trivial(ephemeral_project_hash: str) -> None:
    def non_trivial_validation_callback(runner: Runner) -> None:
        project = runner.project
        assert project
        assert project.ontology_structure.objects
        assert project.workflow.stages

    runner = Runner(project_hash=ephemeral_project_hash, pre_execution_callback=non_trivial_validation_callback)

    @runner.stage(AGENT_STAGE_NAME)
    def stage_1() -> None:
        return None

    runner()


@pytest.mark.parametrize(
    "provide_project_hash_at_define_time",
    [
        True,
        False,
    ],
)
def test_project_validation_callback_throws(
    ephemeral_project_hash: str, provide_project_hash_at_define_time: bool
) -> None:
    def throwing_callback(runner: Runner) -> None:
        assert False

    runner = Runner(
        project_hash=ephemeral_project_hash if provide_project_hash_at_define_time else None,
        pre_execution_callback=throwing_callback,
    )

    @runner.stage(AGENT_STAGE_NAME)
    def stage_1() -> None:
        return None

    with pytest.raises(AssertionError):
        runner(project_hash=ephemeral_project_hash if not provide_project_hash_at_define_time else None)


@pytest.mark.parametrize(
    "pathway_name", [pytest.param(True, id="Pass an incorrect name"), pytest.param(False, id="Pass an incorrect UUID")]
)
def test_runner_throws_error_if_wrong_pathway(ephemeral_project_hash: str, pathway_name: bool) -> None:
    runner = Runner(project_hash=ephemeral_project_hash)

    wrong_pathway: str | UUID = "Not the name of the pathway" if pathway_name else uuid4()

    @runner.stage(AGENT_STAGE_NAME)
    def agent_function(task: AgentTask) -> str | UUID:
        return wrong_pathway

    # Run the runner
    with pytest.raises(PrintableError) as e:
        runner()
    if pathway_name:
        assert AGENT_TO_COMPLETE_PATHWAY_NAME in str(e)
    else:
        assert AGENT_TO_COMPLETE_PATHWAY_HASH in str(e)


def test_queue_runner_resolves_agent_stage(ephemeral_project_hash: str) -> None:
    runner = Runner(project_hash=ephemeral_project_hash)

    @runner.stage(AGENT_STAGE_NAME)
    def agent_func(stage: AgentStage) -> str:
        assert stage
        assert stage.title == AGENT_STAGE_NAME
        assert stage.pathways
        pathway = stage.pathways[0]
        assert pathway.name == AGENT_TO_COMPLETE_PATHWAY_NAME
        assert pathway.uuid == AGENT_TO_COMPLETE_PATHWAY_HASH
        return pathway.name

    runner()


def test_runner_storage_item_dependency_resolved_once(ephemeral_image_project_hash: str) -> None:
    runner = Runner(project_hash=ephemeral_image_project_hash)

    @runner.stage(AGENT_STAGE_NAME)
    def storage_dep(label_row: LabelRowV2, storage_item: StorageItem) -> None:
        assert storage_item
        assert storage_item.uuid == label_row.backing_item_uuid

    with patch.object(StorageItem, "_get_item") as mock_get_item:
        with patch.object(StorageItem, "_get_items", side_effect=StorageItem._get_items) as mock_get_items:
            runner()
            mock_get_item.assert_not_called()
            mock_get_items.assert_called_once()

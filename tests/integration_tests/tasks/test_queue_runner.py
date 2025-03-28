from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from encord.client import EncordClientProject
from encord.constants.enums import DataType
from encord.objects.coordinates import BoundingBoxCoordinates
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.ontology_object import Object
from encord.workflow.stages.agent import AgentStage, AgentTask
from encord.workflow.stages.final import FinalStage

from encord_agents.exceptions import PrintableError
from encord_agents.tasks import QueueRunner
from encord_agents.tasks.models import TaskAgentReturnStruct, TaskCompletionResult
from tests.fixtures import (
    AGENT_STAGE_NAME,
    AGENT_TO_COMPLETE_PATHWAY_HASH,
    AGENT_TO_COMPLETE_PATHWAY_NAME,
    BBOX_ONTOLOGY_HASH,
    COMPLETE_STAGE_NAME,
)


def test_list_agent_stages(ephemeral_project_hash: str) -> None:
    queue_runner = QueueRunner(project_hash=ephemeral_project_hash)
    with pytest.raises(StopIteration):
        next(iter(queue_runner.get_agent_stages()))

    @queue_runner.stage(AGENT_STAGE_NAME)
    def agent_func() -> None:
        return None

    agent_stages_iter = iter(queue_runner.get_agent_stages())
    stage = next(agent_stages_iter)
    assert stage.title == AGENT_STAGE_NAME
    with pytest.raises(StopIteration):
        next(agent_stages_iter)


def test_queue_runner_e2e(ephemeral_project_hash: str, mock_agent: MagicMock) -> None:
    queue_runner = QueueRunner(project_hash=ephemeral_project_hash)

    @queue_runner.stage(AGENT_STAGE_NAME)
    def agent_func(agent_task: AgentTask) -> str:
        mock_agent(agent_task)
        return AGENT_TO_COMPLETE_PATHWAY_NAME

    queue: list[str] = []
    for stage in queue_runner.get_agent_stages():
        for task in stage.get_tasks():
            queue.append(task.model_dump_json())
    assert queue_runner.project
    N_items = len(queue_runner.project.list_label_rows_v2())
    assert len(queue) == N_items

    agent_stage = queue_runner.project.workflow.get_stage(name=AGENT_STAGE_NAME, type_=AgentStage)
    agent_stage_tasks = list(agent_stage.get_tasks())
    # Haven't actually moved the tasks yet
    assert len(agent_stage_tasks) == N_items
    final_stage = queue_runner.project.workflow.get_stage(name=COMPLETE_STAGE_NAME, type_=FinalStage)
    final_stage_tasks = list(final_stage.get_tasks())
    assert len(final_stage_tasks) == 0

    while queue:
        task_spec = queue.pop()
        agent_task = AgentTask.model_validate_json(task_spec)
        result_json = agent_func(task_spec)
        result = TaskCompletionResult.model_validate_json(result_json)
        assert result.success
        assert not result.error
        assert result.pathway == UUID(AGENT_TO_COMPLETE_PATHWAY_HASH)
        assert result.stage_uuid == agent_stage.uuid
        assert result.task_uuid == agent_task.uuid

    # Have moved the tasks
    agent_stage_tasks = list(agent_stage.get_tasks())
    assert len(agent_stage_tasks) == 0
    final_stage_tasks = list(final_stage.get_tasks())
    assert len(final_stage_tasks) == N_items

    assert mock_agent.call_count == N_items


def test_queue_runner_passes_errors_appropriately(ephemeral_project_hash: str) -> None:
    queue_runner = QueueRunner(project_hash=ephemeral_project_hash)

    @queue_runner.stage(AGENT_STAGE_NAME)
    def agent_func(agent_task: AgentTask) -> str:
        raise Exception()
        return AGENT_TO_COMPLETE_PATHWAY_NAME

    queue: list[str] = []
    for stage in queue_runner.get_agent_stages():
        for task in stage.get_tasks():
            queue.append(task.model_dump_json())
    assert queue_runner.project
    N_items = len(queue_runner.project.list_label_rows_v2())
    # Check exception not thrown fetching tasks and they are added to Queue appropriately
    assert len(queue) == N_items
    agent_stage = queue_runner.project.workflow.get_stage(name=AGENT_STAGE_NAME, type_=AgentStage)

    while queue:
        task_spec = queue.pop()
        agent_task = AgentTask.model_validate_json(task_spec)
        result_json = agent_func(task_spec)
        result = TaskCompletionResult.model_validate_json(result_json)
        assert not result.success
        assert result.error
        assert "Exception" in result.error
        assert result.pathway is None
        assert result.stage_uuid == agent_stage.uuid
        assert result.task_uuid == agent_task.uuid

    agent_stage_tasks = list(agent_stage.get_tasks())
    # Haven't actually moved the tasks yet
    assert len(agent_stage_tasks) == N_items
    final_stage = queue_runner.project.workflow.get_stage(name=COMPLETE_STAGE_NAME, type_=FinalStage)
    final_stage_tasks = list(final_stage.get_tasks())
    assert len(final_stage_tasks) == 0


@pytest.mark.parametrize(
    "pathway_name", [pytest.param(True, id="Pass an incorrect name"), pytest.param(False, id="Pass an incorrect UUID")]
)
def test_runner_throws_error_if_wrong_pathway(ephemeral_project_hash: str, pathway_name: bool) -> None:
    queue_runner = QueueRunner(project_hash=ephemeral_project_hash)

    wrong_pathway: str | UUID = "Not the name of the pathway" if pathway_name else uuid4()

    @queue_runner.stage(AGENT_STAGE_NAME)
    def agent_function(task: AgentTask) -> str | UUID:
        return wrong_pathway

    queue: list[str] = []
    for stage in queue_runner.get_agent_stages():
        for task in stage.get_tasks():
            queue.append(task.model_dump_json())

    while queue:
        task_spec = queue.pop()
        with pytest.raises(PrintableError) as e:
            agent_function(task_spec)
        if pathway_name:
            assert AGENT_TO_COMPLETE_PATHWAY_NAME in str(e)
        else:
            assert AGENT_TO_COMPLETE_PATHWAY_HASH in str(e)


def test_queue_runner_return_struct_object(ephemeral_project_hash: str) -> None:
    queue_runner = QueueRunner(project_hash=ephemeral_project_hash)

    assert queue_runner.project
    bbox_object = queue_runner.project.ontology_structure.get_child_by_hash(BBOX_ONTOLOGY_HASH, type_=Object)
    N_items = len(queue_runner.project.list_label_rows_v2())

    @queue_runner.stage(AGENT_STAGE_NAME)
    def update_label_row(label_row: LabelRowV2) -> TaskAgentReturnStruct:
        if label_row.data_type in [DataType.AUDIO, DataType.PLAIN_TEXT]:
            # TODO: Make instances of objects for these data types
            return TaskAgentReturnStruct(pathway=AGENT_TO_COMPLETE_PATHWAY_HASH, label_row=label_row)
        obj_instance = bbox_object.create_instance()
        obj_instance.set_for_frames(BoundingBoxCoordinates(height=0.5, width=0.5, top_left_x=0, top_left_y=0))
        label_row.add_object_instance(obj_instance)
        return TaskAgentReturnStruct(pathway=AGENT_TO_COMPLETE_PATHWAY_HASH, label_row=label_row)

    queue: list[str] = []
    for stage in queue_runner.get_agent_stages():
        for task in stage.get_tasks():
            queue.append(task.model_dump_json())

    # Check tasks are added to Queue appropriately
    assert len(queue) == N_items

    with patch.object(
        EncordClientProject, "save_label_rows", side_effect=EncordClientProject.save_label_rows, autospec=True
    ) as save_label_rows_patch:
        while queue:
            task_spec = queue.pop()
            result_json = update_label_row(task_spec)
            result = TaskCompletionResult.model_validate_json(result_json)
            assert result.success
            assert not result.error
            assert result.pathway == UUID(AGENT_TO_COMPLETE_PATHWAY_HASH)

        # Verify save_label_rows was called appropriately
        assert save_label_rows_patch.call_count > 0

    # Verify the objects were added to the label rows
    lrs = queue_runner.project.list_label_rows_v2()
    with queue_runner.project.create_bundle() as bundle:
        for row in lrs:
            row.initialise_labels(bundle=bundle)
    for row in lrs:
        if row.data_type in [DataType.AUDIO, DataType.PLAIN_TEXT]:
            continue
        assert row.get_object_instances()

    # Verify tasks were moved from agent stage to final stage
    agent_stage = queue_runner.project.workflow.get_stage(name=AGENT_STAGE_NAME, type_=AgentStage)
    agent_stage_tasks = list(agent_stage.get_tasks())
    assert len(agent_stage_tasks) == 0

    final_stage = queue_runner.project.workflow.get_stage(name=COMPLETE_STAGE_NAME, type_=FinalStage)
    final_stage_tasks = list(final_stage.get_tasks())
    assert len(final_stage_tasks) == N_items

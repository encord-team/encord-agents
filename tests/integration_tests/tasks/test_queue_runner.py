from unittest.mock import MagicMock

import pytest
from encord.user_client import EncordUserClient
from encord.workflow.stages.agent import AgentStage, AgentTask
from encord.workflow.stages.final import FinalStage

from encord_agents.core.utils import batch_iterator
from encord_agents.tasks import QueueRunner
from encord_agents.tasks.models import TaskCompletionResult
from tests.fixtures import (
    AGENT_STAGE_NAME,
    AGENT_TO_COMPLETE_PATHWAY_NAME,
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
        assert result.pathway == AGENT_TO_COMPLETE_PATHWAY_NAME
        assert result.stage_uuid == agent_stage.uuid
        assert result.task_uuid == agent_task.uuid

    # Have moved the tasks
    agent_stage_tasks = list(agent_stage.get_tasks())
    assert len(agent_stage_tasks) == 0
    final_stage_tasks = list(final_stage.get_tasks())
    assert len(final_stage_tasks) == N_items

    assert mock_agent.call_count == N_items

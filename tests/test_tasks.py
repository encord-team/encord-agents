from datetime import datetime
from unittest.mock import patch

import pytest
import time_machine

from encord_agents.exceptions import PrintableError
from encord_agents.tasks.runner import SequentialRunner


def test_overrride_runner() -> None:
    runner = SequentialRunner()

    @runner.stage(stage="Yep")
    def method_1() -> str:
        return "1"

    with pytest.raises(PrintableError):

        @runner.stage(stage="Yep")
        def method_2() -> str:
            return "2"

    @runner.stage(stage="Yep", overwrite=True)
    def method_3() -> str:
        return "3"

    assert len(runner.agents) == 1
    agent_YEP = runner.agents[0]
    assert agent_YEP.callable() == "3"


def test_override_runner_preserves_order() -> None:
    runner = SequentialRunner()

    @runner.stage(stage="Stage1")
    def method_1() -> str:
        return "1"

    @runner.stage(stage="Stage2")
    def method_2() -> str:
        return "2"

    @runner.stage(stage="Stage1", overwrite=True)
    def method_3() -> str:
        return "3"

    assert len(runner.agents) == 2
    assert [agent.identity for agent in runner.agents] == ["Stage1", "Stage2"]

    agent_stage1 = runner.agents[0]
    assert agent_stage1.callable() == "3"

    agent_stage2 = runner.agents[1]
    assert agent_stage2.callable() == "2"


def test_max_tasks_per_stage_validation() -> None:
    runner = SequentialRunner()

    with pytest.raises(PrintableError):
        runner(max_tasks_per_stage=-1)
    # Actual behaviour checked in integration_tests/tasks/test_queue_runner via integration test


def test_runner_refresh_every(ephemeral_project_hash: str) -> None:
    refresh_every = 5
    cycles_to_run = 3
    sleeps: list[int] = []
    runner = SequentialRunner(project_hash=ephemeral_project_hash)

    class StopAfterNTasks(Exception):
        pass

    @runner.stage("Stage1")
    def method_1() -> None:
        pass

    with time_machine.travel(datetime(2025, 1, 1, 12, 0, 0), tick=False) as traveller:

        def fake_sleep(secs: int) -> None:
            sleeps.append(secs)
            traveller.shift(secs)  # jump the clock forward
            if len(sleeps) >= cycles_to_run:
                raise StopAfterNTasks()

        with patch("encord_agents.tasks.runner.sequential_runner.time.sleep", fake_sleep):
            with pytest.raises(StopAfterNTasks):
                runner(refresh_every=refresh_every)

    assert len(sleeps) == cycles_to_run
    assert sum(sleeps) == refresh_every * cycles_to_run

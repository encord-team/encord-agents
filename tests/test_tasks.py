import pytest
from typer import BadParameter

from encord_agents.exceptions import PrintableError
from encord_agents.tasks.runner import Runner


def test_overrride_runner() -> None:
    runner = Runner()

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


def test_max_tasks_per_stage_validation() -> None:
    runner = Runner()

    with pytest.raises(PrintableError):
        runner(max_tasks_per_stage=-1)
    # As is, can't test actually making max_tasks without major re-factor / mocking

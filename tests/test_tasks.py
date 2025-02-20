import pytest

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

from encord_agents.aws.wrappers import editor_agent as aws_editor_agent
from encord_agents.core.data_model import FrameData
from encord_agents.gcp.wrappers import editor_agent as gcp_editor_agent


def test_serverless() -> None:
    @aws_editor_agent()
    def aws_editor_agent_fn(frame_data: FrameData) -> None:
        pass

    @gcp_editor_agent()
    def gcp_editor_agent_fn(frame_data: FrameData) -> None:
        pass

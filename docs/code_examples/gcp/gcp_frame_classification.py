import os

from anthropic import Anthropic
from encord.objects.ontology_labels_impl import LabelRowV2
from numpy.typing import NDArray
from typing_extensions import Annotated

from encord_agents.core.ontology import OntologyDataModel
from encord_agents.core.utils import get_user_client
from encord_agents.core.video import Frame
from encord_agents.gcp import Depends, editor_agent
from encord_agents.gcp.dependencies import FrameData, dep_single_frame

client = get_user_client()
project = client.get_project("<your_project_hash>")

# Data model
data_model = OntologyDataModel(project.ontology_structure.classifications)

system_prompt = f"""
You're a helpful assistant that's supposed to help fill in json objects 
according to this schema:

    ```json
    {data_model.model_json_schema_str}
    ```

Please only respond with valid json.
"""

# Prompts
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)


@editor_agent()
def agent(
    frame_data: FrameData,
    lr: LabelRowV2,
    content: Annotated[NDArray, Depends(dep_single_frame)],
):
    frame = Frame(frame_data.frame, content=content)
    message = anthropic_client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [frame.b64_encoding(output_format="anthropic")],
            }
        ],
    )
    try:
        classifications = data_model(message.content[0].text)
        for clf in classifications:
            clf.set_for_frames(frame_data.frame, confidence=0.5, manual_annotation=False)
            lr.add_classification_instance(clf)
    except Exception:
        import traceback

        traceback.print_exc()
        print(f"Response from model: {message.content[0].text}")

    lr.save()

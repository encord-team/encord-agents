# 1. Import dependencies, authenticate with Encord, and set up the Project. Ensure you insert your Project's unique identifier.
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

# 2. Create a data model and a system prompt based on the Project Ontology to tell Claude how to structure its response
data_model = OntologyDataModel(project.ontology_structure.classifications)

system_prompt = f"""
You're a helpful assistant that's supposed to help fill in json objects 
according to this schema:

    ```json
    {data_model.model_json_schema_str}
    ```

Please only respond with valid json.
"""

# 3. Set up an Anthropic API client to establish communication with Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)


# 4. Define the Editor Agent
@editor_agent()
def agent(
    frame_data: FrameData,
    lr: LabelRowV2,
    content: Annotated[NDArray, Depends(dep_single_frame)],
):
    # # Retrieving Frame Content: It automatically fetches the current frame's image data using the `dep_single_frame` dependency
    frame = Frame(frame_data.frame, content=content)
    # Analyzing with Claude: The frame image is then sent to the Claude AI model for analysis
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
        # Parsing Classifications: Claude's response is parsed and transformed into structured classification instances using the predefined data model
        classifications = data_model(message.content[0].text)
        for clf in classifications:
            clf.set_for_frames(frame_data.frame, confidence=0.5, manual_annotation=False)
            lr.add_classification_instance(clf)
    except Exception:
        import traceback

        traceback.print_exc()
        print(f"Response from model: {message.content[0].text}")

    # Saving Results: The new classifications are added to the active label row, and the updated results are saved within the Project.
    lr.save()

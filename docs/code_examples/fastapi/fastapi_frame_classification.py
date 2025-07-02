# 1. Import dependencies and set up the Project. The CORS middleware is crucial as it allows the Encord platform to make requests to your API.
import os

import numpy as np
from anthropic import Anthropic
from encord.objects.ontology_labels_impl import LabelRowV2
from fastapi import Depends
from numpy.typing import NDArray
from typing_extensions import Annotated

from encord_agents.core.data_model import Frame
from encord_agents.core.ontology import OntologyDataModel
from encord_agents.core.utils import get_user_client
from encord_agents.fastapi.cors import get_encord_app
from encord_agents.fastapi.dependencies import (
    FrameData,
    dep_label_row,
    dep_single_frame,
)

# Initialize FastAPI app
app = get_encord_app()

# 2. Set up the Project and create a data model based on the Ontology.

client = get_user_client()
project = client.get_project("<your_project_hash>")
data_model = OntologyDataModel(project.ontology_structure.classifications)

# 3. Set up Claude and create the system prompt that tells Claude how to structure its response.
system_prompt = f"""
You're a helpful assistant that's supposed to help fill in json objects 
according to this schema:

    ```json
    {data_model.model_json_schema_str}
    ```

Please only respond with valid json.
"""

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)


# 4. Define the Editor Agent
@app.post("/frame_classification")
async def classify_frame(
    frame_data: FrameData,
    lr: Annotated[LabelRowV2, Depends(dep_label_row)],
    content: Annotated[NDArray[np.uint8], Depends(dep_single_frame)],
):
    # Receives frame data using FastAPI's Form dependency.
    # Note: FastAPI handles parsing the incoming request body (which implicitly includes frame_data,
    # and the dependencies (dep_label_row, dep_single_frame) resolve the lr and content).

    """Classify a frame using Claude."""
    # Constructs a `Frame` object with the content.
    frame = Frame(frame=frame_data.frame, content=content)

    # Sends the frame image to Claude for analysis.
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
        # Parses Claude's response into classification instances.
        classifications = data_model(message.content[0].text)
        for clf in classifications:
            clf.set_for_frames(frame_data.frame, confidence=0.5, manual_annotation=False)
            # Adds classifications to the label row
            lr.add_classification_instance(clf)
    except Exception:
        import traceback

        traceback.print_exc()
        print(f"Response from model: {message.content[0].text}")

    # Saves the updated data.
    lr.save()

# 1. Import dependencies, authenticate with Encord, and set up the Project. Ensure you insert your Project's unique identifier
import os

from anthropic import Anthropic
from encord.objects.ontology_labels_impl import LabelRowV2
from typing_extensions import Annotated

from encord_agents.core.ontology import OntologyDataModel
from encord_agents.core.utils import get_user_client
from encord_agents.gcp import Depends, editor_agent
from encord_agents.gcp.dependencies import FrameData, InstanceCrop, dep_object_crops

# User client
client = get_user_client()
project = client.get_project("<project_hash>")

# 2. Extract the generic Ontology object and the specific objects of interest. This example sorts Ontology objects based on whether their title is `"generic"`
generic_ont_obj, *other_objects = sorted(
    project.ontology_structure.objects,
    key=lambda o: o.title.lower() == "generic",
    reverse=True,
)

# 3. Prepare the system prompt for each object crop using the `data_model` to generate the JSON schema
data_model = OntologyDataModel(other_objects)
system_prompt = f"""
You're a helpful assistant that's supposed to help fill in 
json objects according to this schema:

`{data_model.model_json_schema_str}`

Please only respond with valid json.
"""

# 4. Set up an Anthropic API client to establish communication with the Claude model. You must include your Anthropic API key

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)


# 5. Define the Editor Agent
@editor_agent()
def agent(
    frame_data: FrameData,
    lr: LabelRowV2,
    crops: Annotated[
        list[InstanceCrop],
        Depends(dep_object_crops(filter_ontology_objects=[generic_ont_obj])),
    ],
):
    # 6. Query Claude using the image crops. The `crop` variable has a convenient `b64_encoding` method to produce an input that Claude understands.
    changes = False
    for crop in crops:
        message = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [crop.b64_encoding(output_format="anthropic")],
                }
            ],
        )

        # 7. Parse Claude's message using the `data_model`.
        try:
            instance = data_model(message.content[0].text)

            coordinates = crop.instance.get_annotation(frame=frame_data.frame).coordinates
            instance.set_for_frames(
                coordinates=coordinates,
                frames=frame_data.frame,
                confidence=0.5,
                manual_annotation=False,
            )
            lr.remove_object(crop.instance)
            lr.add_object_instance(instance)
            changes = True
        except Exception:
            import traceback

            traceback.print_exc()
            print(f"Response from model: {message.content[0].text}")

    # 8. Save the labels with Encord.
    if changes:
        lr.save()

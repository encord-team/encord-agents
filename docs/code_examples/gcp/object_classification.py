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
generic_ont_obj, *other_objects = sorted(
    project.ontology_structure.objects,
    key=lambda o: o.title.lower() == "generic",
    reverse=True,
)

# Data model
data_model = OntologyDataModel(other_objects)
system_prompt = f"""
You're a helpful assistant that's supposed to help fill in 
json objects according to this schema:

`{data_model.model_json_schema_str}`

Please only respond with valid json.
"""

# Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)


# Setup agent
@editor_agent()
def agent(
    frame_data: FrameData,
    lr: LabelRowV2,
    crops: Annotated[
        list[InstanceCrop],
        Depends(dep_object_crops(filter_ontology_objects=[generic_ont_obj])),
    ],
):
    # Query Claude
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

        # Parse result
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

    # Save changes
    if changes:
        lr.save()

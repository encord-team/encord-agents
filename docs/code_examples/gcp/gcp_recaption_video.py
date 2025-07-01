# 1. Set up imports and create a Pydantic model for our LLM's structured output.
import os
from typing import Annotated

import numpy as np
from encord.exceptions import LabelRowError
from encord.objects.classification_instance import ClassificationInstance
from encord.objects.ontology_labels_impl import LabelRowV2
from langchain_openai import ChatOpenAI
from numpy.typing import NDArray
from pydantic import BaseModel

from encord_agents import FrameData
from encord_agents.gcp import Depends, editor_agent
from encord_agents.gcp.dependencies import Frame, dep_single_frame


# The response model for the agent to follow.
class AgentCaptionResponse(BaseModel):
    rephrase_1: str
    rephrase_2: str
    rephrase_3: str


# 2. Create a detailed system prompt for the LLM that explains exactly what kind of rephrasing we want.
SYSTEM_PROMPT = """
You are a helpful assistant that rephrases captions.

I will provide you with a video caption and an image of the scene of the video. 

The captions follow this format:

"The droid picks up <cup_0> and puts it on the <table_0>."

The captions that you make should replace the tags, e.g., <cup_0>, with the actual object names.
The replacements should be consistent with the scene.

Here are three rephrases: 

1. The droid picks up the blue mug and puts it on the left side of the table.
2. The droid picks up the cup and puts it to the left of the plate.
3. The droid is picking up the mug on the right side of the table and putting it down next to the plate.

You will rephrase the caption in three different ways, as above, the rephrases should be

1. Diverse in terms of adjectives, object relations, and object positions.
2. Sound in relation to the scene. You cannot talk about objects you cannot see.
3. Short and concise. Keep it within one sentence.

"""

# 3. Configure the LLM to use structured outputs based on our model.
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4, api_key=os.environ["OPENAI_API_KEY"])
llm_structured = llm.with_structured_output(AgentCaptionResponse)


# 4. Create a helper function to prompt the model with both text and image.
def prompt_gpt(caption: str, image: Frame) -> AgentCaptionResponse:
    prompt = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"Video caption: `{caption}`"},
                image.b64_encoding(output_format="openai"),
            ],
        },
    ]
    return llm_structured.invoke(prompt)


# 5. Define the agent to handle the recaptioning. This includes:
@editor_agent()
def my_agent(
    frame_data: FrameData,
    label_row: LabelRowV2,  # FrameData is automatically received by the agent
    frame_content: Annotated[NDArray[np.uint8], Depends(dep_single_frame)],
) -> None:
    # Retrieve the existing human-created caption, prioritizing captions from the current frame or falling back to frame zero.
    cap, *rs = label_row.ontology_structure.classifications

    # Read the existing human caption
    instances = label_row.get_classification_instances(
        filter_ontology_classification=cap, filter_frames=[0, frame_data.frame]
    )
    if not instances:
        # nothing to do if there are no human labels
        return
    elif len(instances) > 1:

        def order_by_current_frame_else_frame_0(
            instance: ClassificationInstance,
        ) -> bool:
            try:
                instance.get_annotation(frame_data.frame)
                return 2  # The best option
            except LabelRowError:
                pass
            try:
                instance.get_annotation(0)
                return 1
            except LabelRowError:
                return 0

        instance = sorted(instances, key=order_by_current_frame_else_frame_0)[-1]
    else:
        instance = instances[0]

    # Read the actual string caption
    caption = instance.get_answer()

    # Send the first frame of the video along with the human caption to the LLM.
    frame = Frame(frame=0, content=frame_content)
    response = prompt_gpt(caption, frame)

    # Process the response from the LLM, which provides three alternative phrasings of the original caption.
    # Update the label row with the new captions, replacing any existing ones.
    # Upsert the new captions
    for r, t in zip(rs, [response.rephrase_1, response.rephrase_2, response.rephrase_3]):
        # Overwrite any existing re-captions
        existing_instances = label_row.get_classification_instances(filter_ontology_classification=r)
        for existing_instance in existing_instances:
            label_row.remove_classification(existing_instance)

        # Create new instances
        ins = r.create_instance()
        ins.set_answer(t, attribute=r.attributes[0])
        ins.set_for_frames(0)
        label_row.add_classification_instance(ins)

    label_row.save()

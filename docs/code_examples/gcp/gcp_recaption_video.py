"""
This example demonstrate how to use `gpt-4o-mini` to recaption videos.

The example applies to Projects with videos and an
Ontology with four text classifications:

1. A text classification containing a summary of 
    what is happening in the video, created by a human.
2-4. Text classification for the LLM to fill in.

The workflow for this agent is as follows:

1. A human sees the video and types in a caption in the first text field.
2. Then, the agent is triggered and the three other captions will be 
    filled in for the human to review and potentially correct.

[Click here](https://agents-docs.encord.com/notebooks/recaption_video/) for a concrete Vision Language Action model use-case.

This example has the following dependencies:

'''file=requirements.txt
encord-agents
langchain-openai
functions-framework
openai
'''

You can copy the above requirements to a requirements.txt file
and run the following commands to test it.

'''shell
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt

ENCORD_SSH_KEY_FILE=/path/to/your_private_key \
OPENAI_API_KEY=<your-api-key> \
functions-framework --target=my_agent --debug --source main.py
'''

In a separate terminal, you can test the agent by running the following command:

'''shell
source venv/bin/activate
encord-agents test local my_agent <url_from_the_label_editor>
'''

Find more instructions on, e.g., hosting the agent see [here](https://agents-docs.encord.com/editor_agents/gcp/).
"""

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


# System prompt for the LLM to follow.
# You should tailor this to your needs.
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

# Make an llm instance that follows structured outputs.
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4, api_key=os.environ["OPENAI_API_KEY"])
llm_structured = llm.with_structured_output(AgentCaptionResponse)


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


# Define the agent. This is the function that will be running
# as an API endpoint on GCP. Notice the name which is the
# name that we use in the `functions-framework ...` command above.
@editor_agent()
def my_agent(
    frame_data: FrameData,
    label_row: LabelRowV2,
    frame_content: Annotated[NDArray[np.uint8], Depends(dep_single_frame)],
) -> None:
    # Get the relevant ontology information
    # Recall that we expect
    # [human annotation, llm recaption 1, llm recaption 2, llm recaption 3]
    # in the Ontology
    cap, *rs = label_row.ontology_structure.classifications

    # Read the existing human caption if there are more captions,
    # we'll take the one from the current frame if it exists
    # otherwise the one from frame zero or any caption, in said order.
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

    # Run the first frame of the video and the human caption
    # against the llm
    frame = Frame(frame=0, content=frame_content)
    response = prompt_gpt(caption, frame)

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

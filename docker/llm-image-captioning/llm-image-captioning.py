import argparse
from typing import Annotated

import numpy as np
from encord.objects.attributes import TextAttribute
from encord.objects.classification import Classification
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.project import Project
from numpy.typing import NDArray
from openai import OpenAI

from encord_agents.core.data_model import Frame
from encord_agents.tasks import Depends, Runner
from encord_agents.tasks.dependencies import dep_single_frame

# Create OpenAI client
openai_client = OpenAI()


def call_openai_captioning(frame: Frame) -> str:
    prompt = """Please provide a caption of the following image. Don't respond with anything else and just immediately proceed into the caption.
  Keep it within 20 words"""

    # Call openai
    response = openai_client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {  # type: ignore[misc,list-item]
                "role": "user",
                "content": [{"type": "text", "text": prompt}, frame.b64_encoding(output_format="openai")],
            }
        ],
    )
    model_response = response.choices[0].message.content or "Failed to get resp"
    return model_response


def dep_classification(project: Project) -> tuple[Classification, TextAttribute]:
    classification = project.ontology_structure.get_child_by_title("Caption", type_=Classification)
    assert classification.attributes
    assert len(classification.attributes) == 1
    text_attr = classification.get_child_by_title("Caption", type_=TextAttribute)
    return classification, text_attr


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process the project hash.")

    # Add the project-hash argument
    parser.add_argument("--project-hash", type=str, required=True, help="Hash value of the project")

    # Parse the arguments
    args = parser.parse_args()
    project_hash = args.project_hash
    runner = Runner(project_hash=project_hash)
    assert runner.valid_stages, "No agent stage found"
    workflow_stage = runner.valid_stages[0]
    assert workflow_stage.pathways, "Require at least one pathway (This should be impossible)"

    @runner.stage("image captioning")
    def agent_image_captioning(
        lr: LabelRowV2,  # <- Automatically injected
        frame: Annotated[NDArray[np.uint8], Depends(dep_single_frame)],
        cls_attr_pair: Annotated[tuple[Classification, TextAttribute], Depends(dep_classification)],
    ) -> str:
        frame_obj = Frame(frame=0, content=frame)
        modeL_response = call_openai_captioning(frame_obj)
        text_classification_obj, text_attr = cls_attr_pair
        cls_instance = text_classification_obj.create_instance()
        cls_instance.set_answer(answer=modeL_response, attribute=text_attr, overwrite=True)
        cls_instance.set_for_frames(0, overwrite=True)
        lr.add_classification_instance(cls_instance, force=True)
        lr.save()
        return workflow_stage.pathways[0].name

    runner.run()

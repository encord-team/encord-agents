import argparse
import logging
from typing import Annotated

import numpy as np
from encord.constants.enums import DataType
from encord.objects.attributes import TextAttribute
from encord.objects.classification import Classification
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.project import Project
from numpy.typing import NDArray
from openai import OpenAI

from encord_agents.core.data_model import Frame, LabelRowInitialiseLabelsArgs
from encord_agents.tasks import Depends, Runner
from encord_agents.tasks.dependencies import dep_single_frame

# Create OpenAI client
openai_client = OpenAI()
logger = logging.getLogger()


def call_openai_captioning(frame: Frame) -> str:
    prompt = """Please provide a caption of the following image. Don't respond with anything else and just immediately proceed into the caption.
  Keep it within 20 words"""

    # Call openai
    response = openai_client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {  # type: ignore[misc,list-item,unused-ignore]
                "role": "user",
                "content": [{"type": "text", "text": prompt}, frame.b64_encoding(output_format="openai")],
            }
        ],
    )
    model_response = response.choices[0].message.content or "Failed to get resp"
    return model_response


def dep_classification(project: Project) -> tuple[Classification, TextAttribute]:
    for classification in project.ontology_structure.classifications:
        if is_text_classification(classification):
            text_attr = classification.get_child_by_title(classification.title, type_=TextAttribute)
            return classification, text_attr
    raise ValueError("Should be impossible")


def is_text_classification(classification: Classification) -> bool:
    if classification.attributes and len(classification.attributes) == 1:
        attr = classification.attributes[0]
        if isinstance(attr, TextAttribute):
            return True
    return False


def validate_project(runner: Runner) -> None:
    assert runner.project
    project = runner.project
    lrs = project.list_label_rows_v2()
    assert all(lr.data_type == DataType.IMAGE for lr in lrs)
    assert project.ontology_structure.classifications
    classifications = project.ontology_structure.classifications

    assert any(is_text_classification(classification=classification) for classification in classifications)

    assert runner.valid_stages
    if len(runner.valid_stages) > 1:
        logger.warning("There are more than one agent stage. We will pick the first")

    agent_stage = runner.valid_stages[0]
    if len(agent_stage.pathways) > 1:
        logger.warning("There are more than one agent pathway. We will pick the first")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process the project hash.")

    # Add the project-hash argument
    parser.add_argument("--project-hash", type=str, required=True, help="Hash value of the project")

    # Parse the arguments
    args = parser.parse_args()
    project_hash = args.project_hash
    runner = Runner(project_hash=project_hash, pre_execution_callback=validate_project)
    runner.was_called_from_cli = True
    assert runner.valid_stages, "No agent stage found"
    workflow_stage = runner.valid_stages[0]
    assert workflow_stage.pathways, "Require at least one pathway (This should be impossible)"

    @runner.stage(
        workflow_stage.title,
        label_row_initialise_labels_args=LabelRowInitialiseLabelsArgs(include_classification_feature_hashes=set()),
    )
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

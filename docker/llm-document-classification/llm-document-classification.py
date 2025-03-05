import argparse
import logging
from pathlib import Path
from typing import Annotated

import openai
from encord.constants.enums import DataType
from encord.objects.attributes import RadioAttribute
from encord.objects.classification import Classification
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.project import Project

from encord_agents.core.data_model import LabelRowInitialiseLabelsArgs
from encord_agents.tasks import Depends, Runner
from encord_agents.tasks.dependencies import dep_asset

openai_client = openai.OpenAI()
logger = logging.getLogger()


def call_openai_captioning(document_contents: str, choices: list[str]) -> str:
    prompt = f"""You are classifying the following text.
    Please respond with one of the following options:
    OPTIONS: {choices}

    The text now commences:
    ============
    {document_contents}
    """

    # Call openai
    response = openai_client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )
    model_response = response.choices[0].message.content or "Failed to get resp"
    model_response = model_response.lower().strip()
    if model_response not in choices:
        logger.exception(f"Failed to get response belonging to {choices=}, got: {model_response}")
        # Will re-try at Agent level
        raise ValueError

    return model_response


def dep_classification(project: Project) -> tuple[Classification, RadioAttribute]:
    for classification in project.ontology_structure.classifications:
        if is_radio_classification(classification):
            radio_attr = classification.get_child_by_title(classification.title, type_=RadioAttribute)
            return classification, radio_attr
    raise ValueError("Should be impossible")


def is_radio_classification(classification: Classification) -> bool:
    if classification.attributes and len(classification.attributes) == 1:
        attr = classification.attributes[0]
        if isinstance(attr, RadioAttribute):
            return True
    return False


def validate_project(runner: Runner) -> None:
    assert runner.project
    project = runner.project
    lrs = project.list_label_rows_v2()
    assert all(lr.data_type == DataType.PLAIN_TEXT for lr in lrs)
    assert project.ontology_structure.classifications
    classifications = project.ontology_structure.classifications

    assert sum(is_radio_classification(classification=classification) for classification in classifications) == 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process the project hash.")

    # Add the project-hash argument
    parser.add_argument("--project-hash", type=str, required=True, help="Hash value of the project")

    # Parse the arguments
    args = parser.parse_args()
    project_hash = args.project_hash
    runner = Runner(project_hash=project_hash, pre_execution_callback=validate_project)
    assert runner.project
    runner.was_called_from_cli = True
    assert runner.valid_stages, "No agent stage found"
    workflow_stage = runner.valid_stages[0]
    assert workflow_stage.pathways, "Require at least one pathway (This should be impossible)"

    @runner.stage(
        workflow_stage.title,
        label_row_initialise_labels_args=LabelRowInitialiseLabelsArgs(include_classification_feature_hashes=set()),
    )
    def clip_image_classification(
        lr: LabelRowV2,  # <- Automatically injected
        path: Annotated[Path, Depends(dep_asset)],
        cls_attr_pair: Annotated[tuple[Classification, RadioAttribute], Depends(dep_classification)],
    ) -> str:
        document_contents = path.read_text()
        text_classification_obj, radio_attr = cls_attr_pair
        choice = call_openai_captioning(document_contents, [option.label.lower() for option in radio_attr.options])
        choice_option = next(option for option in radio_attr.options if option.label.lower() == choice.lower())
        cls_instance = text_classification_obj.create_instance(range_only=True)
        cls_instance.set_answer(answer=choice_option, attribute=radio_attr, overwrite=True)
        cls_instance.set_for_frames(0, overwrite=True)
        lr.add_classification_instance(cls_instance, force=True)
        lr.save()
        return workflow_stage.pathways[0].name

    runner.run()

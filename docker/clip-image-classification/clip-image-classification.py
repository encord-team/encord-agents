import argparse
import logging
import os
from pathlib import Path
from typing import Annotated

import clip
import torch
from clip.model import CLIP
from encord.constants.enums import DataType
from encord.objects.attributes import RadioAttribute
from encord.objects.classification import Classification
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.project import Project
from PIL import Image

from encord_agents.core.data_model import LabelRowInitialiseLabelsArgs
from encord_agents.tasks import Depends, Runner
from encord_agents.tasks.dependencies import dep_asset

# Load the model
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device)
assert isinstance(model, CLIP)
print("Model loaded")
logger = logging.getLogger()


def get_text_embeddings(choices: list[str]) -> torch.Tensor:
    text_inputs = torch.cat([clip.tokenize(choice) for choice in choices]).to(device)
    with torch.no_grad():
        text_features: torch.Tensor = model.encode_text(text_inputs)
    text_features /= text_features.norm(dim=-1, keepdim=True)
    return text_features


def classify_with_clip(frame: Image.Image, text_features: torch.Tensor) -> int:
    """Return the index of the chosen text feature"""
    image = preprocess(frame).unsqueeze(0).to(device)
    with torch.no_grad():
        image_feature: torch.Tensor = model.encode_image(image)
    image_feature /= image_feature.norm(dim=-1, keepdim=True)
    similarity = (image_feature @ text_features.T).softmax(dim=-1)
    return int(similarity.argmax())


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
    assert all(lr.data_type == DataType.IMAGE for lr in lrs)
    assert project.ontology_structure.classifications
    classifications = project.ontology_structure.classifications

    assert sum(is_radio_classification(classification=classification) for classification in classifications) == 1

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
    assert runner.project
    runner.was_called_from_cli = True
    assert runner.valid_stages, "No agent stage found"
    workflow_stage = runner.valid_stages[0]
    assert workflow_stage.pathways, "Require at least one pathway (This should be impossible)"

    _, radio_attr = dep_classification(runner.project)
    choices = [option.label for option in radio_attr.options]
    text_features = get_text_embeddings(choices)

    @runner.stage(
        workflow_stage.title,
        label_row_initialise_labels_args=LabelRowInitialiseLabelsArgs(include_classification_feature_hashes=set()),
    )
    def clip_image_classification(
        lr: LabelRowV2,  # <- Automatically injected
        path: Annotated[Path, Depends(dep_asset)],
        cls_attr_pair: Annotated[tuple[Classification, RadioAttribute], Depends(dep_classification)],
    ) -> str:
        index_of_chosen_class = classify_with_clip(Image.open(path), text_features)
        text_classification_obj, radio_attr = cls_attr_pair
        chosen_class_option = radio_attr.options[index_of_chosen_class]
        cls_instance = text_classification_obj.create_instance()
        cls_instance.set_answer(answer=chosen_class_option, attribute=radio_attr, overwrite=True)
        cls_instance.set_for_frames(0, overwrite=True)
        lr.add_classification_instance(cls_instance, force=True)
        lr.save()
        return workflow_stage.pathways[0].name

    runner.run()

import argparse
import os
from typing import Annotated

import requests
import torch
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.orm.storage import StorageItemType
from encord.storage import StorageItem
from huggingface_hub import login
from transformers import AutoProcessor, Gemma3ForConditionalGeneration

from encord_agents.core.data_model import LabelRowInitialiseLabelsArgs
from encord_agents.core.utils import download_asset
from encord_agents.core.video import iter_video
from encord_agents.tasks import Depends, Runner
from encord_agents.tasks.dependencies import dep_storage_item

login(os.getenv("HUGGINGFACE_API_KEY"))

model_id = "google/gemma-3-4b-it"

model = Gemma3ForConditionalGeneration.from_pretrained(model_id, device_map="auto").eval()

processor = AutoProcessor.from_pretrained(model_id)


def call_gemma_text_reasoning(text_body: str, choices: list[str]) -> str:
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "You are a helpful assistant, designed to filter documents to certain pathways dependant on the documents contents. You will select from a set of pathways and respond with exactly that pathway",
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""Please select one of the following pathways: {choices} to represent the following document: 
                    {text_body}""",
                },
            ],
        },
    ]

    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device, dtype=torch.bfloat16)

    input_len = inputs["input_ids"].shape[-1]

    with torch.inference_mode():
        generation = model.generate(**inputs, max_new_tokens=100, do_sample=False)
        generation = generation[0][input_len:]

    response = processor.decode(generation, skip_special_tokens=True)

    if response not in choices:
        # Will re-try at Agent level
        print("Got response", response)
        print("Wanted", choices)
        raise ValueError

    return response  # type: ignore[no-any-return]


def call_gemma_image_reasoning(image_url: str, choices: list[str]) -> str:
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "You are a helpful assistant, designed to filter images to certain pathways dependant on the images contents. You will select from a set of pathways and respond with exactly that pathway",
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "image", "url": image_url},
                {
                    "type": "text",
                    "text": f"Please select one of the following pathways: {choices}",
                },
            ],
        },
    ]

    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device, dtype=torch.bfloat16)

    input_len = inputs["input_ids"].shape[-1]

    with torch.inference_mode():
        generation = model.generate(**inputs, max_new_tokens=100, do_sample=False)
        generation = generation[0][input_len:]

    response = processor.decode(generation, skip_special_tokens=True)
    response = response.strip()

    if response not in choices:
        # Will re-try at Agent level
        print("Got response", response)
        print("Wanted", choices)
        raise ValueError

    return response  # type: ignore[no-any-return]


def call_gemma_reasoning(storage_item: StorageItem, label_row: LabelRowV2, choices: list[str]) -> str:
    if storage_item.item_type == StorageItemType.PLAIN_TEXT:
        url = storage_item.get_signed_url()
        assert url
        url_resp = requests.get(url)
        text_body = url_resp.text
        return call_gemma_text_reasoning(text_body, choices)
    elif storage_item.item_type == StorageItemType.IMAGE:
        url = storage_item.get_signed_url()
        assert url
        return call_gemma_image_reasoning(url, choices)
    elif storage_item.item_type == StorageItemType.VIDEO:
        with download_asset(storage_item, None) as asset:
            first_frame = next(iter_video(asset))
            url_repr = first_frame.b64_encoding(output_format="url")
            return call_gemma_image_reasoning(url_repr, choices)
    else:
        print(storage_item)
        raise ValueError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process the project hash.")

    # Add the project-hash argument
    parser.add_argument("--project-hash", type=str, required=True, help="Hash value of the project")
    parser.add_argument(
        "--max-tasks-per-stage",
        type=int,
        required=False,
        help="Max tasks per stage",
    )

    # Parse the arguments
    args = parser.parse_args()
    project_hash = args.project_hash
    max_tasks_per_stage = args.max_tasks_per_stage
    runner = Runner(project_hash=project_hash)
    assert runner.project
    runner.was_called_from_cli = True
    assert runner.valid_stages, "No agent stage found"
    workflow_stage = runner.valid_stages[0]
    assert workflow_stage.pathways, "Require at least one pathway (This should be impossible)"
    choices = [pathway.name for pathway in workflow_stage.pathways]

    @runner.stage(
        workflow_stage.title,
        label_row_initialise_labels_args=LabelRowInitialiseLabelsArgs(include_classification_feature_hashes=set()),
    )
    def gemma_pathway_choice(
        label_row: LabelRowV2,
        storage_item: Annotated[StorageItem, Depends(dep_storage_item)],
    ) -> str:
        pathway_choice = call_gemma_reasoning(storage_item, label_row, choices=choices)
        return pathway_choice

    runner.run()

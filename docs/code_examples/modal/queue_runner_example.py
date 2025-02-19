"""
# Modal Queue Runner Example

This example demonstrates how to use Modal.com to process Encord Agents tasks in a distributed way.

## Prerequisites

- A Modal account and CLI setup (https://modal.com/docs/guide)
- Encord Agents package installed
- An Encord project to process
- Modal SSH key secret configured (named "encord-ssh-key")

## Overview

This example shows how to:

1. Configure a Modal app with required dependencies
2. Set up a QueueRunner to manage Encord tasks
3. Define an agent stage as a Modal function
4. Process tasks in parallel using Modal's distributed computing

## How it Works

The example:
1. Creates a Modal app with a Debian-based environment
2. Sets up a QueueRunner connected to an Encord project
3. Defines a simple agent that extracts the last 8 characters of label titles
4. Processes tasks in parallel using Modal's map functionality

## Usage

1. Ensure Modal CLI is configured:
   ```bash
   modal token new
   ```

2. Set up your Modal SSH key secret:
   ```bash
   modal secret create encord-ssh-key
   ```

3. Run the example:
   ```bash
   modal run queue_runner_example.py
   ```

## Code Structure

- `APP_NAME`: Defines the Modal app name
- `stage_1`: Main agent function decorated with Modal and QueueRunner
- `last_eight`: Helper function to process label rows
- `main`: Entry point that executes the parallel processing

## Configuration

Update these values for your use case:
- `project_hash`: Your Encord project hash
- `concurrency_limit`: Number of parallel executions (default: 5)
"""

from typing import Iterable
from uuid import UUID
from typing_extensions import Annotated
from encord.objects.ontology_labels_impl import LabelRowV2
from encord_agents.tasks import QueueRunner, Depends
from encord_agents.tasks.models import TaskCompletionResult

import modal

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "git",
        "libgl1",
        "libglib2.0-0",
    ).pip_install(
        "fastapi[standard]",
        "encord-agents",
        "modal",
    )
)
APP_NAME = "my-job-queue"
app = modal.App(name=APP_NAME, image=image)

runner = QueueRunner(project_hash="<project-hash>")

def last_eight(lr: LabelRowV2) -> str:
    return lr.data_title[-8:]

# Define the agent stage and put it in a (remote) modal function 
@app.function(
    secrets=[modal.Secret.from_name("encord-ssh-key")],
    concurrency_limit=5,
)
@runner.stage("<agent-stage>")
def stage_1(
    prefix: Annotated[str, Depends(last_eight)]
):
    print(f"From agent: {prefix}")
    return "<path-name-to-follow>"

# Define the main function that will be executed when the modal is run
# to populate the queue with tasks
@app.local_entrypoint()
def main():
    for stage in runner.get_agent_stages():
        # Remote execution of function on tasks
        result_strings: list[str] = list(
            stage_1.map(
                [t.model_dump_json() for t in stage.get_tasks()]
            )
        )

        print(stage.title)
        completion_result = TaskCompletionResult.model_validate_json(result_strings[0])
        print(f"Example completion result: {completion_result}")




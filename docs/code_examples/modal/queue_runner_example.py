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

## Setting up authentication

You need to [authenticate](../authentication.md) with Encord first.
Once you have a private ssh key (preferably corresponding to a service account), you should also ensure that you have [signed up for Modal](https://modal.com/signup).

Now you can configure the secret:

1. Go to [https://modal.com/secrets](https://modal.com/secrets)
2. Click "Create new secret"
3. Choose the "Custom" option
4. Name it `encord-ssh-key` (ensure that any name you choose matches the name in the code below)
5. Add an environment variable names `ENCORD_SSH_KEY` with the content of your private ssh key file. Similar to the figure below.

This setup allows `encord-agents` to authenticate with Encord using the provided key.

## Usage

```bash
modal run queue_runner_example.py
```

You can follow the progress of the tasks on the Modal dashboard: [https://modal.com/apps](https://modal.com/apps)

## Code Structure

- `APP_NAME`: Defines the Modal app name
- `stage_1`: Main agent function decorated with Modal and QueueRunner
- `last_eight`: Helper function to process label rows
- `main`: Entry point that executes the parallel processing

## Configuration

Update the following values for your use case:

- `project_hash`: Your Encord project hash
- `concurrency_limit`: Number of parallel executions (default: 5)
"""

from typing import Iterable
from uuid import UUID

import modal
from encord.objects.ontology_labels_impl import LabelRowV2
from typing_extensions import Annotated

from encord_agents.tasks import Depends, QueueRunner
from encord_agents.tasks.models import TaskCompletionResult

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "git",
        "libgl1",
        "libglib2.0-0",
    )
    .pip_install(
        "fastapi[standard]",
        "encord-agents",
        "modal",
    )
)
APP_NAME = "<app-name>"
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
def stage_1(prefix: Annotated[str, Depends(last_eight)]):
    print(f"From agent: {prefix}")
    return "<path-name-to-follow>"


# Define the main function to be executed when the modal is run
# to populate the queue with tasks
@app.local_entrypoint()
def main():
    for stage in runner.get_agent_stages():
        # Remote execution of function on tasks
        result_strings: list[str] = list(stage_1.map([t.model_dump_json() for t in stage.get_tasks()]))

        print(stage.title)
        completion_result = TaskCompletionResult.model_validate_json(result_strings[0])
        print(f"Example completion result: {completion_result}")

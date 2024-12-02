The `Runner` class is the core component for building task agents in Encord.
It provides a simple interface for defining agent logic and handling task progression in Encord workflows.

## Overview

The Runner manages the execution of agent logic on tasks within specific workflow stages.
It:

- Connects directly to your Encord project via the encode [SDK](https://docs.encord.com/sdk-documentation/getting-started-sdk/installation-sdk){ target="\_blank", rel="noopener noreferrer" }.
- Provide function decorators to associate the functions with workflow stages
- Manages retries and error handling
- Handles task fetching and updates
- Optimizes performance through batched updates and data loading

## Basic Usage

The basic usage pattern of the `Runner` looks like the following.
You follow three steps:

1. Initialize the runner
2. Implement the logic for each stage in your workflow you want to capture with the runner.
3. Execute the runner

```python title="example_agent.py"
from encord.objects.ontology_labels_impl import LabelRowV2
from encord_agents.tasks import Runner

# Step 1: Initialization
# Initialize the runner
# project hash is optional but allows you to "fail fast" 
# if you misconfigure the stages.
runner = Runner(project_hash="<your_project_hash>")

# Step 2: Definition
# Define agent logic for a specific stage
@runner.stage(stage="my_stage_name")  # or stage="<stage_uuid>"
def process_task(lr: LabelRowV2) -> str | None:
    # Modify the label row as needed
    lr.set_priority(0.5)

    # Return the pathway name or UUID where the task should go next
    return "next_stage"

# Step 3: Execution
if __name__ == "__main__":
    # via the CLI
    runner.run()

    # or via code
    # simple
    runner()
    # args
    runner(
        project_hash="<your_project_hash">,
        refresh_every: int | None = None,
        num_retries: int = 1,
        task_batch_size: int = 1,
    )
```

To execute the runner via the CLI, you can do:

```shell
# simple
python example_agent.py --project-hash <your_project_hash>
# use help for additional configurations
python example_agent.py --help
```

## Running Agents

### Basic Execution

```python
if __name__ == "__main__":
    runner.run()
```

This will:

1. Connect to your Encord project
2. Poll for tasks in the configured stages
3. Execute your agent functions on each task
4. Move tasks according to returned pathway
5. Retry failed tasks up to `num_retries` times

See below for [configuration options](.#runtime-configuration).

### Command Line Interface

The runner exposes configuration via CLI:

```bash
python my_agent.py \
    --project-hash "<project_hash>" \
    --task-batch-size 1 \
    --num-retries 3
    --refresh-every 3600 # seconds
```

### Error Handling

The runner will:

- Retry failed tasks up to `num_retries` times (default: 3)
- Log errors for debugging
- Continue processing other tasks if one fails
- Bundle updates for better performance (configurable via `task_batch_size`)


## Configuration
### Initialization

Initialization specs:
___
::: encord_agents.tasks.runner.Runner.__init__
    options:
        show_if_no_docstring: false
        show_subodules: false
___

### Runtime Configuration

There are two ways to execute the runner. You can run the runner directly from your code:

```python
...
runner = Runner()
...
runner(project_hash="<your_project_hash>")  # See all params below 👇
```

Or you can run it via the command-line interface (CLI):

```python
...
runner = Runner()
...
if __name__ == "__main__":
    runner.run()
```

Both options take same arguments (listed below).
For the CLI, please run

```shell
pythion your_script.py --help
```

to see how to specify them.

___
::: encord_agents.tasks.runner.Runner.__call__
___

When running the agent, you can configure its behavior either through code or CLI arguments:

```python
# Via code
runner(
    task_batch_size=1,  # Control batching of task updates (default: 100)
    num_retries=3,      # Number of retries for failed tasks (default: 3)
)

# Or via CLI
# python my_agent.py --task-batch-size 1 --num-retries 3
```

### Performance Considerations

By default, the Runner bundles task updates for better performance with a batch size of 100. For debugging or when immediate updates are needed, you can set task_batch_size=1:

```shell
# Via CLI
python my_agent.py --task-batch-size 1
```

Or in code

```python
runner(task_batch_size=1)
```

## Stage Decorators

The `@runner.stage` decorator connects your functions to specific stages in your Encord workflow.

```python
@runner.stage(stage: str)
def my_agent(lr: LabelRowV2) -> str | None:
    """
    Args:
        stage: Either the UUID or title of the agent stage in your workflow
    Returns:
        The name or UUID of the pathway where the task should go next,
        or None to leave the task in the current stage
    """
    pass
```

You can define multiple stages in a single runner:

```python
@runner.stage("prelabel")
def prelabel_task(lr: LabelRowV2) -> str:
    # Add initial labels
    return "review"

@runner.stage("validate")
def validate_task(lr: LabelRowV2) -> str:
    # Validate labels
    return "complete"
```

## Dependencies

The Runner supports dependency injection similar to FastAPI. Dependencies are functions that provide common resources or utilities to your agent functions.

### Built-in Dependencies

```python
from typing_extensions import Annotated
from encord.workflow.stages.agent import AgentStage
from encord_agents.tasks import Depends
from encord_agents.tasks.dependencies import (
    Twin,              # Access a "twin" project's labels
    dep_twin_label_row,# Get label row from twin project
    dep_video_iterator # Iterate over video frames
)

@runner.stage("my_stage")
def my_agent(
    task: AgentTask,
    lr: LabelRowV2,
    twin: Annotated[Twin, Depends(dep_twin_label_row(twin_project_hash="..."))],
    frames: Annotated[Iterator[Frame], Depends(dep_video_iterator)]
) -> str:
    # Use the dependencies
    pass
```

### Custom Dependencies

You can create your own dependencies that can also use other dependencies:

```python
from encord.objects.ontology_labels_impl import LabelRowV2

def my_custom_dependency(lr: LabelRowV2) -> dict:
    """Custom dependencies can use LabelRowV2 and other dependencies"""
    return {"metadata": lr.data_title}

@runner.stage("my_stage")
def my_agent(
    metadata: Annotated[dict, Depends(my_custom_dependency)]
) -> str:
    # metadata is automatically injected
    return "next_stage"
```


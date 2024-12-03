The `Runner` class is the core component for building task agents in Encord.
It provides a simple interface for defining agent logic and handling task progression in Encord workflows.

## Overview

The Runner manages the execution of agent logic on tasks within specific workflow stages.
It:

- Connects directly to your Encord project via the Encord [SDK](https://docs.encord.com/sdk-documentation/getting-started-sdk/installation-sdk){ target="\_blank", rel="noopener noreferrer" }
- Provides function decorators to associate the functions with workflow stages
- Manages retries and error handling
- Handles task fetching and updates
- Optimizes performance through batched updates and data loading

## Basic Usage

The basic usage pattern of the `Runner` follows three steps:

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
        refresh_every=3600,  # seconds
        num_retries = 1,
        task_batch_size = 1,
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
runner.run()  # will run the runner as CLI tool
runner()      # will run the runner directly
```

Both will:

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

---

::: encord_agents.tasks.runner.Runner.__init__
    options:
        show_if_no_docstring: false
        show_subodules: false

---

### Runtime Configuration

There are two ways to execute the runner.
You can run the runner directly from your code:

```python
...
runner = Runner()
...
runner(project_hash="<your_project_hash>")  # See all params below 👇
```

Or you can run it via the command-line interface (CLI) by employing the `runner.run()` function.
Suppose you have an `example.py` file that looks like this:

```python title="example.py"
...
runner = Runner()
...
if __name__ == "__main__":
    runner.run()
```

Then, the runner will turn into a CLI tool with the exact same arguments as running it via code:

```shell
$ python example.py --help

 Usage: example.py [OPTIONS]

 Execute the runner.
 Full documentation here: https://agents-docs.encord.com/task_agents/runner

╭─ Options ──────────────────────────────────────────────────────────╮
│ --refresh-every   INTEGER  Fetch task statuses from the Encord     │
│                            Project every `refresh_every` seconds.  │
│                            If `None`, the runner will exit once    │
│                            task queue is empty.                    │
│                            [default: None]                         │
│ --num-retries     INTEGER  If an agent fails on a task, how many   │
│                            times should the runner retry it?       │
│                            [default: 3]                            │
│ --task-batch-size INTEGER  Number of tasks for which labels are    │
│                            loaded into memory at once.             │
│                            [default: 300]                          │
│ --project-hash    TEXT     The project hash if not defined at      │
│                            runner instantiation.                   │
│                            [default: None]                         │
│ --help                     Show this message and exit.             │
╰────────────────────────────────────────────────────────────────────╯
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
@runner.stage(stage = "<stage_name_or_uuid>")
def my_agent(lr: LabelRowV2, ...) -> str | UUID | None:
    """
    Args:
        lr: Automatically injected via by the `Runner`
        ...: See the "Dependencies" section for examples of
             how to, e.g., inject assets, client metadata, and
             more.

    Returns:
        The name or UUID of the pathway where the task should go next,
        or None to leave the task in the current stage.
    """
    pass
```

The `my_agent` function will be called by the runner for every task that's in the specified stage. 
It is supposed to return where the task should go next.
This can be done by pathways names or `UUID`s. 
If None is returned, the task will not move and the runner will pick up that task again in the future.

You can also define multiple stages in a single runner:

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

If you define multiple stages, the task queues for each stage will be emptied one queue at a time in the order in which the stages were defined in the runner.
That is, if you define a runner with two stages:

```
runner = Runner()

@runner.stage("stage_1")
def stage_1():
    return "next"

@runner.stage("stage_2")
def stage_2():
    return "next"
```

The queue for `"stage_1"` will be emptied first and successively the queue for `"stage_2"`. 
If you set the `refresh_every` argument, the runner will poll both queues again after emptying the initial queues. 
In turn, data that came into the queue after the initial poll by the runner will be picked up in the second iteration.
In the case where the time of an execution has already exceeded the `refresh_every` threshold, the agent will poll for new tasks instantly.

To give you an idea about the order of execution, please find the pseudo code below.

```python
# ⚠️  PSEUDO CODE - not intended for copying ⚠️
def execute(self, refresh_every = None):
    timestamp = datetime.now()
    while True:
        # self.agents ≈ [stage_1, stage_2]
        for agent in self.agents:  
            for task in agent.get_tasks():
                # Inject params based on task
                stage.execute(solve_dependencies(task, agent))  

        if refresh_every is None:
            break
        else:
            # repeat after timestamp + timedelta(seconds=refresh_every)
            # or straight away if already exceeded
            ...
```

### Optional arguments

When you wrap a function with the `@runner.stage(...)` wrapper, you can add include a [`label_row_metadata_include_args: LabelRowMetadataIncludeArgs`](../reference/core.md#encord_agents.core.data_model.LabelRowMetadataIncludeArgs) argument which will be passed on to the Encord Project's [`list_label_row_v2` method](https://docs.encord.com/sdk-documentation/sdk-references/project#list-label-rows-v2){ target="\_blank", rel="noopener noreferrer" }. This is useful to, e.g., be able to _read_ the client metadata associated to a task.
Notice, if you need to update the metadata, you will have to use the `dep_storage_item` dependencies.

Here is an example:

```python
args = LabelRowMetadataIncludeArgs(
    include_client_metadata=True,
)
@runner.stage("<my_stage_name>", label_row_metadata_include_args=args)
def my_agent(lr: LabelRowV2):
    lr.client_metadata  # will now be populated
```

## Dependencies

The Runner supports dependency injection similar to FastAPI. Dependencies are functions that provide common resources or utilities to your agent functions.

### Built-in Dependencies

#### Example
The library provides many commonly dependencies. 
Please see the [References section](../reference/task_agents.md#encord_agents.tasks.dependencies) for an explicit list.
In the example below, we show how to obtain both label rows from "twin projects" and a frame iterator for videos -- just by specifying that it's something that the agent function depends on.

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

#### Annotations
There are three object types that you can get without any extensive type annotations.

If you type __any__ parameter of your stage implementation, e.g., the `my_agent` function above, with either of `[AgentTask, Project, LabelRowV2]`, the function will be called with that type of object, matching the task at hand.

That is, if you do:

```python
from encord.project import Project
...

@runner.stage("your_stage_name")
def my_agent(project: Project):
    ...
```

the `project` will be the [workflow project][docs-workflow-project]{ target="\_blank", rel="noopener noreferrer" } instance for the `project_hash` you specified when executing the runner.

Similarly, the `task` and `label_row` (associated with the task) can be obtained as follows:

```python
from encord.objects import LabelRowV2
from encord.workflow.stages.agent import AgentTask

@runner.stage("your_stage_name")
def my_agent(task: AgentTask, label_row: LabelRowV2):
    ...
```

The remaining dependencies must be specified with a `encord_agents.tasks.dependencies.Depends` type annotation using one of the following two patterns.

```python
from typing_extensions import Annotated

from encord.storage import StorageItem
from encord_agents.tasks.dependencies import (
    Depends, 
    dep_storage_item,
)


@runner.stage("your_stage_name")
def my_agent(
    storage_item_1: Annotated[StorageItem, Depends(dep_storage_item)],
    storage_item_2: StorageItem = Depends(dep_storage_item)
):
    ...
```

### Custom Dependencies

Dependencies can actually be any function that has a similar function declaration to the ones above. 
That is, functions that have parameters typed with `AgentTask`, `Project`, `LabelRowV2`, or other dependencies annotated with `Depends`.

You can create your own dependencies that can also use nested dependencies like this:

```python
from encord.objects import LabelRowV2
from encord.storage import StorageItem

def my_custom_dependency(
    lr: LabelRowV2,
    storage_item: StorageItem = Depends(dep_storage_item)
) -> dict:
    """Custom dependencies can use LabelRowV2 and other dependencies"""
    return {
        "data_title": lr.data_title,
        "metadata": storage_item.client_metadata
    }

@runner.stage("my_stage")
def my_agent(
    metadata: Annotated[dict, Depends(my_custom_dependency)]
) -> str:
    # metadata is automatically injected
    return "next_stage"
```

[docs-workflow-project]: https://docs.encord.com/sdk-documentation/projects-sdk/sdk-workflow-projects#workflow-projects

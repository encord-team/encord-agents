The `Runner` classes are the core components for building task agents in Encord.
They provide a simple interface for defining agent logic and moving tasks through the Encord project workflows.


## Stage Decorators

Imagine that you have a workflow with three stages: `start`, `agent`, and `complete`.
The `Runner` objects from `encord_agents.tasks.runner` will allow you to define the logic for the purple stages.
In this case, the `Runner` will allow you to define the logic for the `Agent 1` stage.

=== "Workflow"
    ```mermaid
    %%{init: {"flowchart": {"htmlLabels": false}} }%%
    flowchart LR
        start("Start")
        agent("`name: 'Agent 1'
            uuid: '6011c8...'
        `")
        complete(Complete)

        start --> agent
        agent -->|"`name: 'complete'
                    uuid: '49a786...'`"   | complete

        style start fill:#fafafa,stroke:#404040,stroke-width:1px
        style agent fill:#f9f0ff,stroke:#531dab,stroke-width:1px
        style complete fill:#f6ffed,stroke:#389e0d,stroke-width:1px
    ```
=== "Workflow Specification"
    ```json
    {
        "graphNodes": [
            {
                "uuid": "44dcd137-061e-4b83-b25d-b0c68281d8c4",
                "nodeType": "START",
                "toNode": "6011c844-fb26-438b-b465-0b0825951015"
            },
            {
                "uuid": "6011c844-fb26-438b-b465-0b0825951015",
                "nodeType": "AGENT",
                "title": "Agent 1",
                "pathways": [
                    {
                        "uuid": "49a786f3-5edf-4b94-aff0-3da9042d3bf0",
                        "name": "complete",
                        "targetNode": "7e7598de-612c-40c4-ba08-5dfec8c3ae8f"
                    }
                ]
            },
            {
                "uuid": "7e7598de-612c-40c4-ba08-5dfec8c3ae8f",
                "nodeType": "DONE",
                "title": "Complete",
                "nodeSubtype": "COMPLETED"
            }
        ],
    }
    ```

The `@runner.stage` decorator connects your functions to specific stages in your Encord workflow.
For the workflow above, you would define the logic for the `Agent 1` stage as follows:

```python
@runner.stage(stage = "Agent 1")
# or @runner.stage(stage = "6011c844-fb26-438b-b465-0b0825951015")
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

=== "Runner"
    ```python
    runner = Runner()

    @runner.stage("stage_1")
    def stage_1():
        return "next"

    @runner.stage("stage_2")
    def stage_2():
        return "next"
    ```

=== "QueueRunner"
    ```python
    runner = QueueRunner()

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

The `Runner` classes are the core components for building task agents in Encord.
They provide a simple interface for defining agent logic and moving tasks through the Encord project workflows.

The `Runner`s manage the execution of agent logic on tasks within specific workflow stages.
They are responsible for:

- Connect directly to your Encord project via the Encord [SDK](https://docs.encord.com/sdk-documentation/getting-started-sdk/installation-sdk){ target="\_blank", rel="noopener noreferrer" }
- Provide function decorators to associate your agent logic with workflow stages
- Manage retries and error handling
- Handle task fetching and updates
- Optimize performance through batched updates and data loading

In the following sections, we will go through the different components of the `Runner`s and how to use them.


## Stage Decorators

Imagine that you have a workflow with three stages: `start`, `agent`, and `complete`.
The `Runner` objects from `encord_agents.tasks.runner` allows you to define the logic for the purple stages.
In this case, the `Runner` allows you to define the logic for the `Agent 1` stage.

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

The agent function is supposed to return where the task should go next.
This can be done by pathways names or `UUID`s. 
If None is returned, the task remains in its current stage. It is processed by the runner on the next execution of that stage.

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

If you define multiple stages. Depending on which type of runner you use, the execution logic differs
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
    The `Runner` executes the tasks in the order in which the stages were defined in the runner.
    That is, the tasks are processed in `stage_1` first and in `stage_2` next.

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
    The `QueueRunner` gives you control over the task queues for each stage.
    Please refer to the [QueueRunner documentation](./queue_runner.md) for more information.

### Optional arguments

When you wrap a function with the `@runner.stage(...)` wrapper, you can include a [`label_row_metadata_include_args: LabelRowMetadataIncludeArgs`](../reference/core.md#encord_agents.core.data_model.LabelRowMetadataIncludeArgs) argument to be passed on to the Encord Project's [`list_label_row_v2` method](https://docs.encord.com/sdk-documentation/sdk-references/project#list-label-rows-v2){ target="\_blank", rel="noopener noreferrer" }. This is useful to, e.g., be able to _read_ the client metadata associated to a task.
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

Additionally, when developing your agent in a REPL environment (such as Jupyter notebooks), it can be useful to re-run cells / snippets. By default, when re-running the:

```python
@runner.stage("<my_stage_name>")
def stage():
    ...
```
snippet, the library raises an error as we validate against attempting to define multiple agents for a given stage. If you wish to overwrite the function associated to a given stage, this can be done by:
```python
@runner.stage("<my_stage_name>", overwrite=True)
def stage():
    ...
```
which updates the definition for the given stage on each re-run. It also ensures that the order of execution is preserved; That is, stages are executed in the order in which they were originally defined.

## Dependencies

The Runner supports dependency injection similar to [FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/){ target="\_blank", rel="noopener noreferrer" }. 
Dependencies are functions that provide common resources or utilities to your agent functions.

### Built-in Dependencies

#### Example
The library provides multiple commonly used dependencies. 
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

In the function body above, the `task`, `lr`, `twin`, and `frames` variables will be automatically injected with the respective dependencies.
This gives you the flexibility to only inject the dependencies that you need and focus on the logic of your agent.

#### Annotations
There are three object types that you can get without any extensive type annotations.

If you type __any__ parameter of your stage implementation, e.g., the `my_agent` function above, with either of `[AgentTask, Project, LabelRowV2]`, the function is called with that type of object, matching the task at hand.

That is, if you do:

```python
from encord.project import Project
...

@runner.stage("your_stage_name")
def my_agent(project: Project):
    ...
```

The `project` is the [workflow project][docs-workflow-project]{ target="\_blank", rel="noopener noreferrer" } instance for the `project_hash` that was specified when defining or executing the runner.

Similarly, the `task` and `label_row` (associated with the given task) can be obtained as follows:

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
    # or storage_item_1: StorageItem = Depends(dep_storage_item)
):
    ...
```

### Custom Dependencies

Dependencies can be any function that has a similar function declaration to the ones above. 
Specifically, functions that have parameters typed with `AgentTask`, `Project`, `LabelRowV2`, or other dependencies annotated with `Depends`.

> !!!warning
> 
> Your custom dependencies should not include any default values or additinoal arguments.
> If you need to pass additional arguments, you can do so by wrapping the dependency in a function:
> 
> ```python
> from functools import partial
> def my_dependency(arg1: str, arg2: int):
>     ...
> 
> def my_dependency_with_default_arg(arg1: str, arg2: int = 42):
>     return partial(my_dependency, arg2=arg2)
> 
> @runner.stage("my_stage")
> def my_agent(
>     # Notice the call to the function                                  👇
>     dep: Annotated[MyDependency, Depends(my_dependency_with_default_arg())]  
> ):
>     ...
> ```
> 
> This will allow you to set default values when you call the dependency.


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

## Optional pre-execution agent validation

If you require additional validation that your runner is suitable for your project, e.g: The project has an appropriate ontology, appropriate workflow stages, you can pass an additional `pre_execution_callback` parameter when defining your Runner.

```python

def pre_execution_callback(runner: Runner) -> None:
    assert runner.project
    project = runner.project
    # Throws if child not found
    project.ontology_structure.get_child_by_title("Car")
    assert runner.agents

runner = Runner(pre_execution_callback=pre_execution_callback)
# Won't yet validate

# Define the agent
@runner.stage("Agent stage")
def agent_stage(task: AgentTask) -> str:
    ...
    return "labeled"

if __name__ == "__main__":
    runner.run()
```

Then we can execute the script by: `python agent.py --project-hash=<your-project-hash>` and then before execution, we will fetch the project and run validation. In the validation, you have access to the whole runner object and we ensure that the validation is run after the project is fetched so you can perform arbitrary validation. We perform the validation just before starting to fetch and execute tasks. This allows you to reference agents in your validation as done above.

## Running the runner

There are two different types of runners with different use-cases. They also have two slightly different execution interfaces. 
Please refer to the following pages for more information:

1. [`Runner`](./sequential_runner.md#running-agents):  This is a simple sequential runner to run the agent functions one after the other. It is easier to debug and understand. Use this for simple workflows or for testing out functionality before you scale it with the `QueueRunner`.
2. [`QueueRunner`](./queue_runner.md#basic-usage): This is a more advanced runner that allows you to run the agent functions in parallel. It's useful when you have a lot of tasks to process and you want to speed up the processing time via parallel execution.

## Comparison between `Runner` and `QueueRunner`

The key differences between `QueueRunner` and the sequential `Runner` are:

| Feature | [Runner](./sequential_runner.md) | [QueueRunner](./queue_runner.md) |
|---------|---------|-------------|
| **Execution Model** | Executes tasks sequentially in a single process | Designed for distributed execution across multiple processes |
| **Project Hash** | Optional at initialization | Required at initialization |
| **Function Wrapping** | Executes your function directly with injected dependencies | Additionally wraps your function to handle JSON task specifications |
| **Execution Control** | Handles task polling and execution | You control task distribution and execution through your queue system |
| **Scaling** | Not suitable for scaling | Suitable for scaling |


[docs-workflow-project]: https://docs.encord.com/sdk-documentation/sdk-references/project#workflow-project
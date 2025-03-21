## Overview
The `Runner` executes tasks in a sequential order.
It is useful for debugging and testing the Workflow. 
Use this for simple workflows or for testing out functionality before you scale compute it with the [`QueueRunner`](./queue_runner.md).

## Basic Usage

The basic usage pattern of the `Runner` follows three steps:

1. Initialize the runner
2. Implement the logic for each stage in your Workflow you want to capture with the runner.
3. Execute the runner

The following example shows how to initialize the runner and implement the logic for each stage in your Workflow you want to capture with the runner.

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

Both options:

1. Connect to your Encord project
2. Poll for tasks in the configured stages
3. Execute your agent functions on each task
4. Move tasks according to returned pathway
5. Retry failed tasks up to `num_retries` times

See the [configuration options](.#runtime-configuration) below.

### Command Line Interface

The runner exposes configuration via CLI:

```bash
python my_agent.py \
    --project-hash "<project_hash>" \
    --task-batch-size 1 \
    --num-retries 3
    --refresh-every 3600 # seconds
```

### Order of execution

The queue for `"stage_1"` is emptied first, and successively the queue for `"stage_2"`. 
If you set the `refresh_every` argument, the runner polls both queues again after emptying the initial queues. 
In turn, data that came into the queue after the initial poll by the runner is picked up in the second iteration.
In the case where the time of an execution has already exceeded the `refresh_every` threshold, the agent polls for new tasks instantly.

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

### Error Handling

The runner:

- Retries failed tasks up to `num_retries` times (default: 3). Changes to the label row are not rolled back.
- Logs errors for debugging
- Continues processing other tasks if a task fails
- Bundles updates for better performance (configurable via `task_batch_size`)


## Configuration

### Initialization

::: encord_agents.tasks.runner.sequential_runner.SequentialRunner.__init__
    options:
        show_if_no_docstring: false
        show_subodules: false
        show_root_toc_entry: false

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

Then, the runner functions as a CLI tool, accepting the same arguments as when executed in code.

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

By default, the Runner bundles task updates for better performance with a batch size of 300. For debugging or when immediate updates are needed, you can set task_batch_size=1:

```shell
# Via CLI
python my_agent.py --task-batch-size 1
```

Or in code

```python
runner(task_batch_size=1)
```

Additionally to speed up your label row updates to the encord platform, we allow you to return a struct object and we then handle batch saving the results to ensure that you spend as time as possible running your agent and minimising time spent writing results. To use this speed up, please instead write:

```python
from encord_agents.tasks.models import TaskAgentReturnStruct

@runner.stage("Agent Stage")
def agent_stage(label_row: LabelRowV2, storage_item: StorageItem) -> TaskAgentReturnStruct:
    # Modify the label row in any manner
    # ...
    return TaskAgentReturnStruct(pathway="Modified label", label_row=label_row)

```

We make use of the [bundle method](https://docs.encord.com/sdk-documentation/general-sdk/sdk-bulk-action-best-practices){target="_blank", rel="noopener"} as in our SDK to batch the label row updates, allowing for >10x speedups.

## Scaling with the `QueueRunner`

The [`QueueRunner`](./queue_runner.md) is a more advanced runner that will allow you to process multiple tasks in parallel.
It is useful when you have a lot of tasks to process and you want to speed up the processing time via parallel execution.

Both the `Runner` and the `QueueRunner` share the same interface.
The difference lies in how you execute them.

The `Runner` executes tasks in a sequential order with the `run()` function.
The `QueueRunner` translates your implementations into functions that take in a task specification as a JSON string and returns a `encord_agents.tasks.models.TaskCompletionResult` as a JSON string.
Stringified JSON tasks are used to pass messages over queues that typically don't allow for custom object types.

Here's an example of how the difference manifests:

=== "The (sequential) `Runner`"
    ```python
    runner = Runner()
    @runner.stage("my_stage")
    def my_agent(task: AgentTask, label_row: LabelRowV2):
        ...
    runner()
    ```
=== "The (parallel) `QueueRunner`"
    ```python
    queue_runner = QueueRunner()  # Change the runner to the queue runner
    
    # The implementation stays the same
    @queue_runner.stage("my_stage")
    def my_agent(task: AgentTask, label_row: LabelRowV2):
        ...

    # Change the execution to use the queue runner
    for agent in queue_runner.get_agent_stages():
        your_task_queue = []
        for task in agent.get_tasks():
            your_task_queue.append(task)

        for task in your_task_queue:
            result = my_agent(task)
    ```

    Please refer to the [Celery example](./queue_runner.md) or [Modal example](./queue_runner.md) for more information.


## Comparison with Queue Runner

The key differences between `QueueRunner` and the sequential `Runner` are:

| Feature | [Runner](./sequential_runner.md) | [QueueRunner](./queue_runner.md) |
|---------|---------|-------------|
| **Execution Model** | Executes tasks sequentially in a single process | Designed for distributed execution across multiple processes |
| **Project Hash** | Optional at initialization | Required at initialization |
| **Function Wrapping** | Executes your function directly with injected dependencies | Additionally wraps your function to handle JSON task specifications |
| **Execution Control** | Handles task polling and execution | You control task distribution and execution through your queue system |
| **Scaling** | Not suitable for scaling | Suitable for scaling |


[docs-workflow-project]: https://docs.encord.com/sdk-documentation/projects-sdk/sdk-workflow-projects#workflow-projects

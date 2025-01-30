TODO - intro

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

[docs-workflow-project]: https://docs.encord.com/sdk-documentation/projects-sdk/sdk-workflow-projects#workflow-projects

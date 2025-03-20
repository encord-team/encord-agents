## Overview
The `QueueRunner` is designed for distributed task processing and parallel execution. It allows you to implement agent logic that can be executed across multiple workers or processes, making it ideal for scaling up task processing in production environments.

## Basic Usage

The basic usage pattern of the `QueueRunner` follows these steps:

1. Initialize the queue runner
2. Implement agent logic for Workflow stages
3. Put tasks into a queue system
4. Execute tasks from the queue

Here's a basic example:

```python title="queue_agent.py"
from encord.objects.ontology_labels_impl import LabelRowV2
from encord_agents.tasks import QueueRunner
from encord.workflow.stages.agent import AgentTask

# Step 1: Initialize the queue runner
# project_hash is required for QueueRunner
runner = QueueRunner(project_hash="<your_project_hash>")

# Step 2: Implement agent logic
@runner.stage("my_stage_name")  # or stage="<stage_uuid>"
def process_task(task: AgentTask, lr: LabelRowV2) -> str:
    # Your agent logic here
    lr.set_priority(0.5)
    return "next_stage"  # or return a pathway UUID

# Step 3 & 4: Queue and execute tasks
if __name__ == "__main__":
    # Get all tasks that need processing
    for stage in runner.get_agent_stages():
        # Your queue implementation
        task_queue = []
        
        # Populate queue with task specifications
        for task in stage.get_tasks():
            task_queue.append(task.model_dump_json())
        
        # Process tasks from queue
        while task_queue:
            task_spec = task_queue.pop()
            # The wrapped function handles all dependency injection
            result_json = process_task(task_spec)
            # result_json contains success/failure status and next pathway
```

!!! tip
    To avoid mixing up the agent implementations, we recommend to use a dedicated queue runner for each agent.

## Integration with Queue Systems

The `QueueRunner` is designed to work with various queue systems. Here are examples with popular frameworks:

### Celery Integration

```python title="celery_agent.py"
from celery import Celery
from encord_agents.tasks import QueueRunner

app = Celery('tasks', broker='redis://localhost:6379/0')
runner = QueueRunner(project_hash="<your_project_hash>")

@runner.stage("my_stage")
def process_task(task: AgentTask) -> str:
    # Your processing logic
    return "next_stage"

# Register with Celery
@app.task
def celery_task(task_spec: str) -> str:
    return process_task(task_spec)

# Populate queue
for stage in runner.get_agent_stages():
    for task in stage.get_tasks():
        celery_task.delay(task.model_dump_json())
```

!!! tip
    For a more detailed example, see the [Celery example](https://github.com/encord-team/encord-agents/tree/main/docs/code_examples/celery){target="\_blank" rel="noopener noreferrer"}.

### Modal Integration

```python title="modal_agent.py"
import modal
from encord_agents.tasks import QueueRunner

stub = modal.Stub("agent-tasks")
runner = QueueRunner(project_hash="<your_project_hash>")

@runner.stage("my_stage")
def process_task(task: AgentTask) -> str:
    # Your processing logic
    return "next_stage"

@stub.function
def modal_task(task_spec: str) -> str:
    return process_task(task_spec)

@stub.local_entrypoint()
def main():
    for stage in runner.get_agent_stages():
        for task in stage.get_tasks():
            modal_task.remote(task.model_dump_json())
```

!!! tip
    For a more detailed example, see the [Modal example](https://github.com/encord-team/encord-agents/blob/main/docs/code_examples/modal/queue_runner_example.py){target="\_blank" rel="noopener noreferrer"}.

## Key Concepts

### Task Specification Format

The `QueueRunner` uses JSON strings to pass task specifications between processes:

```python
# Converting task to JSON spec
task_spec = task.model_dump_json()

# The wrapped agent function handles parsing and dependency injection
result = my_agent(task_spec)  # Returns TaskCompletionResult as JSON
```

A task specification is a string in the following format:

```json
{
  "uuid": "<task-uuid>",
  "created_at": "2025-02-19T15:23:09.629049",
  "updated_at": "2025-02-19T15:23:09.679423",
  "status": "NEW",
  "data_hash": "<data-hash>",
  "data_title": "<data-title>",
  "label_branch_name": "<label-branch-name>",
  "assignee": null
}
```

### Task Completion Results

Agent functions return a JSON-serialized `TaskCompletionResult` containing:
- Task UUID
- Stage UUID
- Success status
- Error message (if any)
- Next pathway (if successful)

```json
{
  "task_uuid": "<task-uuid>",
  "stage_uuid": "<stage-uuid>",
  "success": true,
  "pathway": "<returned-pathway-uuid-or-name>",
  "error": null
}
```

### Error Handling

The `QueueRunner` provides error handling at the task level:

```python
from encord_agents.tasks.models import TaskCompletionResult

# The result JSON can be parsed back into a TaskCompletionResult
result = TaskCompletionResult.model_validate_json(result_json)

if not result.error:
    print(f"Task {result.task_uuid} completed, next pathway: {result.pathway}")
else:
    print(f"Task {result.task_uuid} failed: {result.error}")
```

## Configuration

### Initialization

::: encord_agents.tasks.runner.queue_runner.QueueRunner.__init__
    options:
        show_if_no_docstring: false
        show_submodules: false
        show_root_toc_entry: false

### Stage Configuration

The `stage` decorator accepts the same configuration options as the [sequential `Runner`](./runner_intro.md#optional-arguments):

Example:
```python
@runner.stage(
    stage="my_stage",
    label_row_metadata_include_args=LabelRowMetadataIncludeArgs(...),
    label_row_initialise_labels_args=LabelRowInitialiseLabelsArgs(...)
)
def my_agent(task: AgentTask) -> str:
    ...
```

## Comparison with Sequential Runner

The key differences between `QueueRunner` and the sequential `Runner` are:

| Feature | [Runner](./sequential_runner.md) | [QueueRunner](./queue_runner.md) |
|---------|---------|-------------|
| **Execution Model** | Executes tasks sequentially in a single process | Designed for distributed execution across multiple processes |
| **Project Hash** | Optional at initialization | Required at initialization |
| **Function Wrapping** | Executes your function directly with injected dependencies | Additionally wraps your function to handle JSON task specifications |
| **Execution Control** | Handles task polling and execution | You control task distribution and execution through your queue system |
| **Scaling** | Not suitable for scaling | Suitable for scaling |

Choose the `QueueRunner` when you need to:

* Process tasks in parallel  
* Scale processing across multiple machines  
* Integrate with existing queue infrastructure  
* Handle high task volumes efficiently  
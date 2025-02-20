import modal  # tested with modal client version: 0.72.10
from encord.objects.ontology_labels_impl import LabelRowV2
from typing_extensions import Annotated

from encord_agents.tasks import Depends, QueueRunner
from encord_agents.tasks.models import TaskCompletionResult

# 1. Modal configuration
# Define a Docker image with the necessary dependencies
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "libgl1",
        "libglib2.0-0",
    )
    .pip_install(
        "fastapi[standard]",
        "encord-agents",
    )
)

# The modal app that runs the jobs
app = modal.App(name="encord-agents-job-queue", image=image)

# 2. Set up the QueueRunner
runner = QueueRunner(project_hash="<project_hash>")
print("instantiated runner")


# 3. Optional - you can still define your own dependencies
#        that the agent definition will rely on.
def last_eight(lr: LabelRowV2) -> str:
    return lr.data_title[-8:]


# 4. Define the remote function.
@app.function(
    secrets=[modal.Secret.from_name("encord-ssh-key")],
    concurrency_limit=5,
)
@runner.stage("Agent 1")
def stage_1(prefix: Annotated[str, Depends(last_eight)]):
    # 5. The logic that goes into the agent
    print(f"From agent: {prefix}")
    return None


# 6. Execute the agent
@app.local_entrypoint()
def main():
    for stage in runner.get_agent_stages():
        result_strings: list[str] = list(
            stage_1.map(  # Remote execution of function on tasks
                map(
                    lambda t: t.model_dump_json(),  # Call function with serializable strings
                    stage.get_tasks(),
                )
            )
        )

        # Example validation of results
        completion_result = TaskCompletionResult.model_validate_json(result_strings[0])
        print(f"Example completion result: {completion_result}")

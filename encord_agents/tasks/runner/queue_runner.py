import traceback
from contextlib import ExitStack
from functools import wraps
from typing import Any, Callable, Iterable
from uuid import UUID

from encord.objects.ontology_labels_impl import LabelRowV2
from encord.project import Project
from encord.workflow.stages.agent import AgentStage

from encord_agents.core.data_model import LabelRowInitialiseLabelsArgs, LabelRowMetadataIncludeArgs
from encord_agents.core.dependencies.models import Context
from encord_agents.core.dependencies.utils import solve_dependencies
from encord_agents.exceptions import PrintableError
from encord_agents.tasks.models import AgentTaskConfig, TaskAgentReturn, TaskCompletionResult
from encord_agents.tasks.runner.runner_base import RunnerBase
from encord_agents.utils.generic_utils import try_coerce_UUID


class QueueRunner(RunnerBase):
    """
    This class is intended to hold agent implementations.
    It makes it easy to put agent task specifications into
    a queue and then execute them in a distributed fashion.

    Below is a template for how that would work.

    *Example:*
    ```python
    runner = QueueRunner(project_hash="...")

    @runner.stage("Agent 1")
    def my_agent_implementation() -> str:
        # ... do your thing
        return "<pathway_name>"

    # Populate the queue
    my_queue = ...
    for stage in runner.get_agent_stages():
        for task in stage.get_tasks():
            my_queue.append(task.model_dump_json())

    # Execute on the queue
    while my_queue:
        task_spec = my_queue.pop()
        result_json = my_agent_implementation(task_spec)
        result = TaskCompletionResult.model_validate_json(result_json)
    ```
    """

    def __init__(self, project_hash: str | UUID):
        """
        Initialize the QueueRunner with a project hash.

        This is the hash of the project that you want to run the tasks on.

        Args:
            project_hash: The hash of the project to run the tasks on.
        """
        super().__init__(project_hash)
        assert self.project is not None
        self._project: Project = self.project

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        raise NotImplementedError(
            "Calling the QueueRunner is not intended. "
            "Prefer using wrapped functions with, e.g., modal or Celery. "
            "For more documentation, please see the `QueueRunner.stage` documentation below."
        )

    def stage(
        self,
        stage: str | UUID,
        *,
        label_row_metadata_include_args: LabelRowMetadataIncludeArgs | None = None,
        label_row_initialise_labels_args: LabelRowInitialiseLabelsArgs | None = None,
    ) -> Callable[[Callable[..., str | UUID | None]], Callable[[str], str]]:
        """
        Agent wrapper intended for queueing systems and distributed workloads.

        Define your agent as you are used to with dependencies in the method declaration and
        return the pathway from the project workflow that the task should follow upon completion.
        The function will be wrapped in logic that does the following (in pseudo code):

        ```
        @runner.stage("stage_name")
        def my_function(...)
            ...

        # is equivalent to

        def wrapped_function(task_json_spec: str) -> str (result_json):
            task = fetch_task(task_sped)
            resources = load_resources(task)
            pathway = your_function(resources)  # <- this is where your code goes
            task.proceed(pathway)
            return TaskCompletionResult.model_dump_json()
        ```

        When you have an `encord.workflow.stages.agent.AgentTask` instance at hand, let's call
        it `task`, then you can call your `wrapped_function` with `task.model_dump_json()`.
        Similarly, you can put `task.model_dump_json()` int a queue and read from that queue, e.g.,
        from another instance/process, to execute `wrapped_function` there.

        As the pseudo code indicates, `wrapped_function` understands how to take that string from
        the queue and resolve all your defined dependencies before calling `your_function`.
        """
        stage_uuid, printable_name = self._validate_stage(stage)

        def decorator(func: Callable[..., str | UUID | None]) -> Callable[[str], str]:
            runner_agent = self._add_stage_agent(
                stage_uuid,
                func,
                stage_insertion=None,
                printable_name=printable_name,
                label_row_metadata_include_args=label_row_metadata_include_args,
                label_row_initialise_labels_args=label_row_initialise_labels_args,
            )
            include_args = runner_agent.label_row_metadata_include_args or LabelRowMetadataIncludeArgs()
            init_args = runner_agent.label_row_initialise_labels_args or LabelRowInitialiseLabelsArgs()

            try:
                stage = self._project.workflow.get_stage(uuid=runner_agent.identity, type_=AgentStage)
            except ValueError as err:
                # Local binding to help mypy
                error = err

                @wraps(func)
                def null_wrapper(json_str: str) -> str:
                    conf = AgentTaskConfig.model_validate_json(json_str)
                    return TaskCompletionResult(
                        task_uuid=conf.task_uuid,
                        success=False,
                        error=str(error),
                    ).model_dump_json()

                return null_wrapper
            pathway_lookup = {pathway.uuid: pathway.name for pathway in stage.pathways}
            name_lookup = {pathway.name: pathway.uuid for pathway in stage.pathways}

            @wraps(func)
            def wrapper(json_str: str) -> str:
                conf = AgentTaskConfig.model_validate_json(json_str)

                task = next((s for s in stage.get_tasks(data_hash=conf.data_hash)), None)
                if task is None:
                    # TODO logging?
                    return TaskCompletionResult(
                        task_uuid=conf.task_uuid,
                        stage_uuid=stage.uuid,
                        success=False,
                        error="Failed to obtain task from Encord",
                    ).model_dump_json()

                try:
                    context = self._assemble_context(
                        task=task,
                        runner_agent=runner_agent,
                        project=self._project,
                        include_args=include_args,
                        init_args=init_args,
                        stage=stage,
                        client=self.client,
                    )

                    next_stage: TaskAgentReturn = None
                    with ExitStack() as stack:
                        dependencies = solve_dependencies(
                            context=context, dependant=runner_agent.dependant, stack=stack
                        )
                        next_stage = runner_agent.callable(**dependencies.values)
                    next_stage_uuid: UUID | None = None
                    if next_stage is None:
                        # TODO: Should we log that task didn't continue?
                        pass
                    elif next_stage_uuid := try_coerce_UUID(next_stage):
                        if next_stage_uuid not in pathway_lookup.keys():
                            raise PrintableError(
                                f"Runner responded with pathway UUID: {next_stage}, only accept: {[pathway.uuid for pathway in stage.pathways]}"
                            )
                        task.proceed(pathway_uuid=str(next_stage_uuid))
                    else:
                        if next_stage not in [pathway.name for pathway in stage.pathways]:
                            raise PrintableError(
                                f"Runner responded with pathway name: {next_stage}, only accept: {[pathway.name for pathway in stage.pathways]}"
                            )
                        task.proceed(pathway_name=str(next_stage))
                        next_stage_uuid = name_lookup[str(next_stage)]
                    return TaskCompletionResult(
                        task_uuid=task.uuid, stage_uuid=stage.uuid, success=True, pathway=next_stage_uuid
                    ).model_dump_json()
                except PrintableError:
                    raise
                except Exception:
                    # TODO logging?
                    return TaskCompletionResult(
                        task_uuid=task.uuid, stage_uuid=stage.uuid, success=False, error=traceback.format_exc()
                    ).model_dump_json()

            return wrapper

        return decorator

    def get_agent_stages(self) -> Iterable[AgentStage]:
        """
        Get the agent stages for which there exist an agent implementation.

        This function is intended to make it easy to iterate through all current
        agent tasks and put the task specs into external queueing systems like
        Celery or Modal.

        For a concrete example, please see the doc string for the class it self.

        Note that if you didn't specify an implementation (by decorating your
        function with `@runner.stage`) for a given agent stage, the stage will
        not show up by calling this function.

        Returns:
            An iterable over `encord.workflow.stages.agent.AgentStage` objects
            where the runner contains an agent implementation.

        Raises:
            AssertionError: if the runner does not have an associated project.
        """
        for runner_agent in self.agents:
            is_uuid = False
            try:
                UUID(str(runner_agent.identity))
                is_uuid = True
            except ValueError:
                pass

            if is_uuid:
                stage = self._project.workflow.get_stage(uuid=runner_agent.identity, type_=AgentStage)
            else:
                stage = self._project.workflow.get_stage(name=str(runner_agent.identity), type_=AgentStage)
            yield stage

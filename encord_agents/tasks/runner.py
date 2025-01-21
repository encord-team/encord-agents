import os
import time
import traceback
from contextlib import ExitStack
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Iterable, Optional
from uuid import UUID

import rich
from encord.http.bundle import Bundle
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.orm.project import ProjectType
from encord.orm.workflow import WorkflowStageType
from encord.project import Project
from encord.workflow.stages.agent import AgentStage, AgentTask
from encord.workflow.workflow import WorkflowStage
from rich.panel import Panel
from tqdm.auto import tqdm
from typer import Abort, Option
from typing_extensions import Annotated

from encord_agents.core.data_model import LabelRowInitialiseLabelsArgs, LabelRowMetadataIncludeArgs
from encord_agents.core.dependencies.models import Context, DecoratedCallable, Dependant
from encord_agents.core.dependencies.utils import get_dependant, solve_dependencies
from encord_agents.core.utils import get_user_client
from encord_agents.exceptions import PrintableError

from .models import AgentTaskConfig, TaskCompletionResult

TaskAgentReturn = str | UUID | None


class RunnerAgent:
    def __init__(
        self,
        identity: str | UUID,
        callable: Callable[..., TaskAgentReturn],
        printable_name: str | None = None,
        label_row_metadata_include_args: LabelRowMetadataIncludeArgs | None = None,
        label_row_initialise_labels_args: LabelRowInitialiseLabelsArgs | None = None,
    ):
        self.identity = identity
        self.printable_name = printable_name or identity
        self.callable = callable
        self.dependant: Dependant = get_dependant(func=callable)
        self.label_row_metadata_include_args = label_row_metadata_include_args
        self.label_row_initialise_labels_args = label_row_initialise_labels_args

    def __repr__(self) -> str:
        return f'RunnerAgent("{self.printable_name}")'


class RunnerBase:
    @staticmethod
    def verify_project_hash(ph: str | UUID) -> str:
        try:
            ph = str(UUID(str(ph)))
        except ValueError:
            print("Could not read project_hash as a UUID")
            raise Abort()
        return ph

    @staticmethod
    def get_stage_names(valid_stages: list[AgentStage], join_str: str = ", ") -> str:
        return join_str.join(
            [f'[magenta]AgentStage(title="{k.title}", uuid="{k.uuid}")[/magenta]' for k in valid_stages]
        )

    @staticmethod
    def validate_project(project: Project | None) -> None:
        if project is None:
            return
        PROJECT_MUSTS = "Task agents only work for workflow projects that have agent nodes in the workflow."
        assert (
            project.project_type == ProjectType.WORKFLOW
        ), f"Provided project is not a workflow project. {PROJECT_MUSTS}"
        assert (
            len([s for s in project.workflow.stages if s.stage_type == WorkflowStageType.AGENT]) > 0
        ), f"Provided project does not have any agent stages in it's workflow. {PROJECT_MUSTS}"

    def __init__(self, project_hash: str | UUID | None = None):
        """
        Initialize the runner with an optional project hash.

        The `project_hash` will allow stricter stage validation.
        If left unspecified, errors will first be raised during execution of the runner.

        Args:
            project_hash: The project hash that the runner applies to.

                Can be left unspecified to be able to reuse same runner on multiple projects.
        """
        self.project_hash = self.verify_project_hash(project_hash) if project_hash else None
        self.client = get_user_client()

        self.project: Project | None = self.client.get_project(self.project_hash) if self.project_hash else None
        self.validate_project(self.project)

        self.valid_stages: list[AgentStage] | None = None
        if self.project is not None:
            self.valid_stages = [s for s in self.project.workflow.stages if s.stage_type == WorkflowStageType.AGENT]
        self.agents: list[RunnerAgent] = []

    def validate_stage(self, stage: str | UUID) -> tuple[UUID | str, str]:
        """
        Returns stage uuid and printable name.
        """
        printable_name = str(stage)
        try:
            stage = UUID(str(stage))
        except ValueError:
            pass

        if self.valid_stages is not None:
            selected_stage: WorkflowStage | None = None
            for v_stage in self.valid_stages:
                attr = v_stage.title if isinstance(stage, str) else v_stage.uuid
                if attr == stage:
                    selected_stage = v_stage

            if selected_stage is None:
                agent_stage_names = self.get_stage_names(self.valid_stages)
                raise PrintableError(
                    rf"Stage name [blue]`{stage}`[/blue] could not be matched against a project stage. Valid stages are \[{agent_stage_names}]."
                )
            stage = selected_stage.uuid

        if stage in [a.identity for a in self.agents]:
            raise PrintableError(
                f"Stage name [blue]`{printable_name}`[/blue] has already been assigned a function. You can only assign one callable to each agent stage."
            )
        return stage, printable_name

    def _add_stage_agent(
        self,
        identity: str | UUID,
        func: Callable[..., TaskAgentReturn],
        printable_name: str | None,
        label_row_metadata_include_args: LabelRowMetadataIncludeArgs | None,
        label_row_initialise_labels_args: LabelRowInitialiseLabelsArgs | None,
    ) -> RunnerAgent:
        runner_agent = RunnerAgent(
            identity=identity,
            callable=func,
            printable_name=printable_name,
            label_row_metadata_include_args=label_row_metadata_include_args,
            label_row_initialise_labels_args=label_row_initialise_labels_args,
        )
        self.agents.append(runner_agent)
        return runner_agent


class Runner(RunnerBase):
    """
    Runs agents against Workflow projects.

    When called, it will iteratively run agent stages till they are empty.
    By default, runner will exit after finishing the tasks identified at the point of trigger.
    To automatically re-run, you can use the `refresh_every` keyword.

    **Example:**

    ```python title="example_agent.py"
    from uuid import UUID
    from encord_agents.tasks import Runner
    runner = Runner()

    @runner.stage("<workflow_node_name>")
    # or
    @runner.stage("<workflow_node_uuid>")
    def my_agent(task: AgentTask) -> str | UUID | None:
        ...
        return "pathway name"  # or pathway uuid


    runner(project_hash="<project_hash>")  # (see __call__ for more arguments)
    # or
    if __name__ == "__main__":
        # for CLI usage: `python example_agent.py --project-hash "<project_hash>"`
        runner.run()
    ```

    """

    def __init__(self, project_hash: str | None = None):
        """
        Initialize the runner with an optional project hash.

        The `project_hash` will allow stricter stage validation.
        If left unspecified, errors will first be raised during execution of the runner.

        Args:
            project_hash: The project hash that the runner applies to.

                Can be left unspecified to be able to reuse same runner on multiple projects.
        """
        super().__init__(project_hash)
        self.agents: list[RunnerAgent] = []
        self.was_called_from_cli = False

    def stage(
        self,
        stage: str | UUID,
        *,
        label_row_metadata_include_args: LabelRowMetadataIncludeArgs | None = None,
        label_row_initialise_labels_args: LabelRowInitialiseLabelsArgs | None = None,
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        r"""
        Decorator to associate a function with an agent stage.

        A function decorated with a stage is added to the list of stages
        that will be handled by the runner.
        The runner will call the function for every task which is in that
        stage.


        **Example:**

        ```python
        runner = Runner()

        @runner.stage("<stage_name_or_uuid>")
        def my_func() -> str | None:
            ...
            return "<pathway_name or pathway_uuid>"
        ```

        The function declaration can be any function that takes parameters
        that are type annotated with the following types:

        * [Project][docs-project]{ target="\_blank", rel="noopener noreferrer" }: the `encord.project.Project`
            that the runner is operating on.
        * [LabelRowV2][docs-label-row]{ target="\_blank", rel="noopener noreferrer" }: the `encord.objects.LabelRowV2`
            that the task is associated with.
        * [AgentTask][docs-project]{ target="\_blank", rel="noopener noreferrer" }: the `encord.workflow.stages.agent.AgentTask`
            that the task is associated with.
        * Any other type: which is annotated with a [dependency](/dependencies.md)

        All those parameters will be automatically injected when the agent is called.

        **Example:**

        ```python
        from typing import Iterator
        from typing_extensions import Annotated

        from encord.project import Project
        from encord_agents.tasks import Depends
        from encord_agents.tasks.dependencies import dep_video_iterator
        from encord.workflow.stages.agent import AgentTask

        runner = Runner()

        def random_value() -> float:
            import random
            return random.random()

        @runner.stage("<stage_name_or_uuid>")
        def my_func(
            project: Project,
            lr: LabelRowV2,
            task: AgentTask,
            video_frames: Annotated[Iterator[Frame], Depends(dep_video_iterator)],
            custom: Annotated[float, Depends(random_value)]
        ) -> str | None:
            ...
            return "<pathway_name or pathway_uuid>"
        ```

        [docs-project]:    https://docs.encord.com/sdk-documentation/sdk-references/project
        [docs-label-row]:  https://docs.encord.com/sdk-documentation/sdk-references/LabelRowV2
        [docs-agent-task]: https://docs.encord.com/sdk-documentation/sdk-references/AgentTask

        Args:
            stage: The name or uuid of the stage that the function should be
                associated with.
            label_row_metadata_include_args: Arguments to be passed to
                `project.list_label_rows_v2(...)`
            label_row_initialise_labels_args: Arguments to be passed to
                `label_row.initialise_labels(...)`

        Returns:
            The decorated function.
        """
        stage_uuid, printable_name = self.validate_stage(stage)

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            self._add_stage_agent(
                stage_uuid, func, printable_name, label_row_metadata_include_args, label_row_initialise_labels_args
            )
            return func

        return decorator

    @staticmethod
    def _execute_tasks(
        project: Project,
        tasks: Iterable[tuple[AgentTask, LabelRowV2 | None]],
        runner_agent: RunnerAgent,
        # num_threads: int,
        num_retries: int,
        pbar_update: Callable[[float | None], bool | None] | None = None,
    ) -> None:
        with Bundle() as bundle:
            for task, label_row in tasks:
                with ExitStack() as stack:
                    context = Context(project=project, task=task, label_row=label_row)
                    dependencies = solve_dependencies(context=context, dependant=runner_agent.dependant, stack=stack)
                    for attempt in range(num_retries + 1):
                        try:
                            next_stage = runner_agent.callable(**dependencies.values)
                            if next_stage is None:
                                pass
                            elif isinstance(next_stage, UUID):
                                task.proceed(pathway_uuid=str(next_stage), bundle=bundle)
                            else:
                                try:
                                    _next_stage = UUID(next_stage)
                                    task.proceed(pathway_uuid=str(_next_stage), bundle=bundle)
                                except ValueError:
                                    task.proceed(pathway_name=next_stage, bundle=bundle)

                            if pbar_update is not None:
                                pbar_update(1.0)
                            break

                        except KeyboardInterrupt:
                            raise
                        except Exception:
                            print(f"[attempt {attempt+1}/{num_retries+1}] Agent failed with error: ")
                            traceback.print_exc()

    def __call__(
        self,
        refresh_every: Annotated[
            Optional[int],
            Option(
                help="Fetch task statuses from the Encord Project every `refresh_every` seconds. If `None`, the runner will exit once task queue is empty."
            ),
        ] = None,
        num_retries: Annotated[
            int, Option(help="If an agent fails on a task, how many times should the runner retry it?")
        ] = 3,
        task_batch_size: Annotated[
            int, Option(help="Number of tasks for which labels are loaded into memory at once.")
        ] = 300,
        project_hash: Annotated[
            Optional[str], Option(help="The project hash if not defined at runner instantiation.")
        ] = None,
    ) -> None:
        """
        Run your task agent `runner(...)`.

        ???+ info "Self-updating/Polling runner"
            The runner can continuously poll new tasks in the project and execute the defined stage agents.
            To do so, please set the `refresh_every` parameter.
            When set, the runner will re-fetch tasks with at least that amount of time in between polls. If you set the time to, e.g., 1 second, but it takes 60 seconds to empty the task queue, the runner will poll again upon completion of the current task queue.

        Args:
            refresh_every: Fetch task statuses from the Encord Project every `refresh_every` seconds.
                If `None`, the runner will exit once task queue is empty.
            num_retries: If an agent fails on a task, how many times should the runner retry it?
            task_batch_size: Number of tasks for which labels are loaded into memory at once.
            project_hash: The project hash if not defined at runner instantiation.
        Returns:
            None
        """
        # Verify project
        if project_hash is not None:
            project_hash = self.verify_project_hash(project_hash)
            project = self.client.get_project(project_hash)
        elif self.project is not None:
            project = self.project
        else:
            # Should not happen. Validated above but mypy doesn't understand.
            raise ValueError("Have no project to execute the runner on. Please specify it.")

        if project is None:
            import sys

            raise PrintableError(
                f"""Please specify project hash in one of the following ways:  
* At instantiation: [blue]`runner = Runner(project_hash="[green]<project_hash>[/green]")`[/blue]
* When called directly: [blue]`runner(project_hash="[green]<project_hash>[/green]")`[/blue]
* When called from CLI: [blue]`python {sys.argv[0]} --project-hash [green]<project_hash>[/green]`[/blue]
"""
            )

        self.validate_project(project)

        # Verify stages
        valid_stages = [s for s in project.workflow.stages if s.stage_type == WorkflowStageType.AGENT]
        agent_stages: dict[str | UUID, WorkflowStage] = {
            **{s.title: s for s in valid_stages},
            **{s.uuid: s for s in valid_stages},
        }
        try:
            for runner_agent in self.agents:
                fn_name = getattr(runner_agent.callable, "__name__", "agent function")
                separator = f"{os.linesep}\t"
                agent_stage_names = separator + self.get_stage_names(valid_stages, join_str=separator) + os.linesep
                if runner_agent.identity not in agent_stages:
                    suggestion: str
                    if len(valid_stages) == 1:
                        suggestion = f'Did you mean to wrap [blue]`{fn_name}`[/blue] with{os.linesep}[magenta]@runner.stage(stage="{valid_stages[0].title}")[/magenta]{os.linesep}or{os.linesep}[magenta]@runner.stage(stage="{valid_stages[0].uuid}")[/magenta]'
                    else:
                        suggestion = f"""
Please use either name annoitations: 
[magenta]@runner.stage(stage="<exact_stage_name>")[/magenta] 

or uuid annotations:
[magenta]@runner.stage(stage="<exact_stage_uuid>")[/magenta] 

For example, if we use the first agent stage listed above, we can use:
[magenta]@runner.stage(stage="{valid_stages[0].title}")
def {fn_name}(...):
    ...
[/magenta]
# or
[magenta]@runner.stage(stage="{valid_stages[0].uuid}")
def {fn_name}(...):
    ...[/magenta]"""
                    raise PrintableError(
                        rf"""Your function [blue]`{fn_name}`[/blue] was annotated to match agent stage [blue]`{runner_agent.printable_name}`[/blue] but that stage is not present as an agent stage in your project workflow. The workflow has following agent stages:

[{agent_stage_names}]

{suggestion}
                        """
                    )

                stage = agent_stages[runner_agent.identity]
                if stage.stage_type != WorkflowStageType.AGENT:
                    raise PrintableError(
                        f"""You cannot use the stage of type `{stage.stage_type}` as an agent stage. It has to be one of the agent stages: 
[{agent_stage_names}]."""
                    )

            # Run
            delta = timedelta(seconds=refresh_every) if refresh_every else None
            next_execution = None

            while True:
                if isinstance(next_execution, datetime):
                    if next_execution > datetime.now():
                        duration = next_execution - datetime.now()
                        print(f"Sleeping {duration.total_seconds()} secs until next execution time.")
                        time.sleep(duration.total_seconds())
                elif next_execution is not None:
                    break

                next_execution = datetime.now() + delta if delta else False
                for runner_agent in self.agents:
                    include_args = runner_agent.label_row_metadata_include_args or LabelRowMetadataIncludeArgs()
                    init_args = runner_agent.label_row_initialise_labels_args or LabelRowInitialiseLabelsArgs()
                    stage = agent_stages[runner_agent.identity]

                    batch: list[AgentTask] = []
                    batch_lrs: list[LabelRowV2 | None] = []

                    tasks = list(stage.get_tasks())
                    pbar = tqdm(desc="Executing tasks", total=len(tasks))
                    for task in tasks:
                        if not isinstance(task, AgentTask):
                            continue
                        batch.append(task)
                        if len(batch) == task_batch_size:
                            batch_lrs = [None] * len(batch)
                            if runner_agent.dependant.needs_label_row:
                                label_rows = {
                                    UUID(lr.data_hash): lr
                                    for lr in project.list_label_rows_v2(
                                        data_hashes=[t.data_hash for t in batch], **include_args.model_dump()
                                    )
                                }
                                batch_lrs = [label_rows.get(t.data_hash) for t in batch]
                                with project.create_bundle() as lr_bundle:
                                    for lr in batch_lrs:
                                        if lr:
                                            lr.initialise_labels(bundle=lr_bundle, **init_args.model_dump())

                            self._execute_tasks(
                                project,
                                zip(batch, batch_lrs),
                                runner_agent,
                                num_retries,
                                pbar_update=pbar.update,
                            )

                            batch = []
                            batch_lrs = []

                    if len(batch) > 0:
                        batch_lrs = [None] * len(batch)
                        if runner_agent.dependant.needs_label_row:
                            label_rows = {
                                UUID(lr.data_hash): lr
                                for lr in project.list_label_rows_v2(
                                    data_hashes=[t.data_hash for t in batch],
                                    **include_args.model_dump(),
                                )
                            }
                            batch_lrs = [label_rows[t.data_hash] for t in batch]
                            with project.create_bundle() as lr_bundle:
                                for lr in batch_lrs:
                                    if lr:
                                        lr.initialise_labels(bundle=lr_bundle, **init_args.model_dump())
                        self._execute_tasks(
                            project, zip(batch, batch_lrs), runner_agent, num_retries, pbar_update=pbar.update
                        )
        except (PrintableError, AssertionError) as err:
            if self.was_called_from_cli:
                panel = Panel(err.args[0], width=None)
                rich.print(panel)
                raise Abort()
            else:
                if isinstance(err, PrintableError):
                    from rich.text import Text

                    plain_text = Text.from_markup(err.args[0]).plain
                    err.args = (plain_text,)
                raise

    def run(self) -> None:
        """
        Execute the runner.

        This function is intended to be called from the "main file".
        It is an entry point to be able to run the agent(s) via your shell
        with command line arguments.

        **Example:**

        ```python title="example.py"
        runner = Runner(project_hash="<your_project_hash>")

        @runner.stage(stage="...")
        def your_func() -> str:
            ...

        if __name__ == "__main__":
            runner.run()
        ```

        You can then run execute the runner with:

        ```shell
        python example.py --help
        ```

        to see the options is has (it's those from `Runner.__call__`).

        """
        from typer import Typer

        self.was_called_from_cli = True
        app = Typer(add_completion=False, rich_markup_mode="rich")
        app.command(
            help=f"Execute the runner.{os.linesep * 2}Full documentation here: https://agents-docs.encord.com/task_agents/runner",
            short_help="Execute the runner as a CLI.",
        )(self.__call__)
        app()


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
        super().__init__(project_hash)
        assert self.project is not None
        self._project: Project = self.project

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        raise NotImplementedError(
            "Calling the QueueRunner is not intended. "
            "Prefer using wrapped functions with, e.g., modal or Celery. "
            "For more documentation, please see the `QueueRunner.stage` documetation below."
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
        stage_uuid, printable_name = self.validate_stage(stage)

        def decorator(func: Callable[..., str | UUID | None]) -> Callable[[str], str]:
            runner_agent = self._add_stage_agent(
                stage_uuid, func, printable_name, label_row_metadata_include_args, label_row_initialise_labels_args
            )
            include_args = runner_agent.label_row_metadata_include_args or LabelRowMetadataIncludeArgs()
            init_args = runner_agent.label_row_initialise_labels_args or LabelRowInitialiseLabelsArgs()

            @wraps(func)
            def wrapper(json_str: str) -> str:
                conf = AgentTaskConfig.model_validate_json(json_str)
                try:
                    stage = self._project.workflow.get_stage(uuid=runner_agent.identity, type_=AgentStage)
                except ValueError as e:
                    return TaskCompletionResult(
                        task_uuid=conf.task_uuid,
                        success=False,
                        error=str(e),
                    ).model_dump_json()

                task = next((s for s in stage.get_tasks(data_hash=conf.data_hash)), None)
                if task is None:
                    # TODO logging?
                    return TaskCompletionResult(
                        task_uuid=conf.task_uuid,
                        stage_uuid=stage.uuid,
                        success=False,
                        error="Failed to obtain task from Encord",
                    ).model_dump_json()

                label_row: LabelRowV2 | None = None
                try:
                    if runner_agent.dependant.needs_label_row:
                        label_row = self._project.list_label_rows_v2(
                            data_hashes=[task.data_hash], **include_args.model_dump()
                        )[0]
                        label_row.initialise_labels(**init_args.model_dump())

                    next_stage: TaskAgentReturn = None
                    with ExitStack() as stack:
                        context = Context(project=self._project, task=task, label_row=label_row)
                        dependencies = solve_dependencies(
                            context=context, dependant=runner_agent.dependant, stack=stack
                        )
                        next_stage = runner_agent.callable(**dependencies.values)

                    if next_stage is None:
                        # TODO: Should we log that task didn't continue?
                        pass
                    elif isinstance(next_stage, UUID):
                        task.proceed(pathway_uuid=str(next_stage))
                    else:
                        try:
                            next_stage = UUID(next_stage)
                            task.proceed(pathway_uuid=str(next_stage))
                        except ValueError:
                            task.proceed(pathway_name=str(next_stage))
                    return TaskCompletionResult(
                        task_uuid=task.uuid, stage_uuid=stage.uuid, success=True, pathway=next_stage
                    ).model_dump_json()
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
            `AssertionError` if the runner does not have an associated project.
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

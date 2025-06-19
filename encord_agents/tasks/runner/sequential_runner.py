import logging
import os
import time
import traceback
from contextlib import ExitStack
from datetime import datetime, timedelta
from typing import Callable, Iterable, Optional
from uuid import UUID

import rich
from encord.http.bundle import Bundle
from encord.orm.workflow import WorkflowStageType
from encord.workflow.stages.agent import AgentStage
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from typer import Abort, Option
from typing_extensions import Annotated, Self

from encord_agents.core.data_model import LabelRowInitialiseLabelsArgs, LabelRowMetadataIncludeArgs
from encord_agents.core.dependencies.models import (
    Context,
    Dependant,
)
from encord_agents.core.dependencies.utils import get_dependant, solve_dependencies
from encord_agents.core.rich_columns import TaskSpeedColumn
from encord_agents.core.utils import batch_iterator
from encord_agents.exceptions import PrintableError
from encord_agents.tasks.models import DecoratedCallable, TaskAgentReturnStruct, TaskAgentReturnType
from encord_agents.tasks.runner.runner_base import RunnerAgent, RunnerBase
from encord_agents.utils.generic_utils import try_coerce_UUID

MAX_LABEL_ROW_BATCH_SIZE = 100


class SequentialRunner(RunnerBase):
    """
    Runs agents against Workflow projects.

    When called, it iteratively runs agent stages until they are empty.
    By default, runner exits after finishing the tasks identified at the point of trigger.
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

    def __init__(
        self,
        project_hash: str | None = None,
        *,
        pre_execution_callback: Callable[[Self], None] | None = None,
    ):
        """
        Initialize the runner with an optional project hash.

        The `project_hash` allows stricter stage validation.
        If left unspecified, errors are only raised during execution of the runner.

        Args:
            project_hash: The project hash that the runner applies to.

                Can be left unspecified to be able to reuse same runner on multiple projects.
            pre_execution_callback: Callable[RunnerBase, None]

                Allows for optional additional validation e.g. Check specific Ontology form
        """
        super().__init__(project_hash)
        self.agents: list[RunnerAgent] = []
        self.was_called_from_cli = False
        self.pre_execution_callback = pre_execution_callback

    def stage(
        self,
        stage: str | UUID,
        *,
        label_row_metadata_include_args: LabelRowMetadataIncludeArgs | None = None,
        label_row_initialise_labels_args: LabelRowInitialiseLabelsArgs | None = None,
        overwrite: bool = False,
        will_set_priority: bool = False,
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        r"""
        Decorator to associate a function with an agent stage.

        A function decorated with a stage is added to the list of stages
        that is handled by the runner.
        The runner calls the function for every task which is in that
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
            overwrite: Overwrite the method associated to this stage if it already exists
                will throw an error otherwise
            will_set_priority: Indicates whether you will be returning a `TaskAgentReturnStruct`
                with a `label_row_priority` field set. This field is only required if you are
                returning the priority of the label row but not depending on the label row it self.
                That is, if your function signature does not include a `LabelRowV2` parameter.

        Returns:
            The decorated function.
        """
        stage_uuid, printable_name = self._validate_stage(stage)
        stage_insertion = self._check_stage_already_defined(stage_uuid, printable_name, overwrite=overwrite)

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            self._add_stage_agent(
                stage_uuid,
                func,
                stage_insertion=stage_insertion,
                printable_name=printable_name,
                label_row_metadata_include_args=label_row_metadata_include_args,
                label_row_initialise_labels_args=label_row_initialise_labels_args,
                will_set_priority=will_set_priority,
            )
            return func

        return decorator

    @staticmethod
    def _execute_tasks(
        contexts: Iterable[Context],
        runner_agent: RunnerAgent,
        stage: AgentStage,
        num_retries: int,
        pbar_update: Callable[[float | None], bool | None] | None = None,
    ) -> None:
        """
        INVARIANT: Tasks should always be for the stage that the runner_agent is associated too
        """
        with Bundle() as task_bundle:
            with Bundle(bundle_size=min(MAX_LABEL_ROW_BATCH_SIZE, len(list(contexts)))) as label_bundle:
                for context in contexts:
                    assert context.task
                    with ExitStack() as stack:
                        task = context.task
                        dependencies = solve_dependencies(
                            context=context, dependant=runner_agent.dependant, stack=stack
                        )
                        for attempt in range(num_retries + 1):
                            try:
                                agent_response: TaskAgentReturnType = runner_agent.callable(**dependencies.values)
                                if isinstance(agent_response, TaskAgentReturnStruct):
                                    pathway_to_follow = agent_response.pathway
                                    if agent_response.label_row:
                                        agent_response.label_row.save(bundle=label_bundle)
                                    if agent_response.label_row_priority:
                                        assert (
                                            context.label_row is not None
                                        ), f"Label row is not set for task {task} setting the priority requires either setting the `will_set_priority` to True on the stage decorator or depending on the label row."
                                        context.label_row.set_priority(
                                            agent_response.label_row_priority, bundle=label_bundle
                                        )
                                else:
                                    pathway_to_follow = agent_response
                                if pathway_to_follow is None:
                                    pass
                                elif next_stage_uuid := try_coerce_UUID(pathway_to_follow):
                                    if next_stage_uuid not in [pathway.uuid for pathway in stage.pathways]:
                                        raise PrintableError(
                                            f"No pathway with UUID: {next_stage_uuid} found. Accepted pathway UUIDs are: {[pathway.uuid for pathway in stage.pathways]}"
                                        )
                                    task.proceed(pathway_uuid=str(next_stage_uuid), bundle=task_bundle)
                                else:
                                    if pathway_to_follow not in [str(pathway.name) for pathway in stage.pathways]:
                                        raise PrintableError(
                                            f"No pathway with name: {pathway_to_follow} found. Accepted pathway names are: {[pathway.name for pathway in stage.pathways]}"
                                        )
                                    task.proceed(pathway_name=str(pathway_to_follow), bundle=task_bundle)
                                if pbar_update is not None:
                                    pbar_update(1.0)
                                break

                            except KeyboardInterrupt:
                                raise
                            except PrintableError:
                                raise
                            except Exception:
                                print(f"[attempt {attempt+1}/{num_retries+1}] Agent failed with error: ")
                                traceback.print_exc()

    def _validate_agent_stages(
        self, valid_stages: list[AgentStage], agent_stages: dict[str | UUID, AgentStage]
    ) -> None:
        for runner_agent in self.agents:
            fn_name = getattr(runner_agent.callable, "__name__", "agent function")
            separator = f"{os.linesep}\t"
            agent_stage_names = separator + self._get_stage_names(valid_stages, join_str=separator) + os.linesep
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
        max_tasks_per_stage: Annotated[
            Optional[int],
            Option(
                help="Max number of tasks to try to process per stage on a given run. If `None`, will attempt all",
            ),
        ] = None,
    ) -> None:
        """
        Run your task agent `runner(...)`.

        ???+ info "Self-updating/Polling runner"
            The runner can continuously poll new tasks in the project and execute the defined stage agents.
            To do so, please set the `refresh_every` parameter.
            When set, the runner re-fetches tasks with at least that amount of time in between polls. If you set the time to, e.g., 1 second, but it takes 60 seconds to empty the task queue, the runner polls again upon completion of the current task queue.

        Args:
            refresh_every: Fetch task statuses from the Encord Project every `refresh_every` seconds.
                If `None`, the runner exits once task queue is empty.
            num_retries: If an agent fails on a task, how many times should the runner retry it?
            task_batch_size: Number of tasks for which labels are loaded into memory at once.
            project_hash: The project hash if not defined at runner instantiation.
        Returns:
            None
        """
        # Verify args that don't depend on external service first
        max_tasks_per_stage = self._validate_max_tasks_per_stage(max_tasks_per_stage)

        # Verify Project
        if project_hash is not None:
            project_hash = self._verify_project_hash(project_hash)
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

        self._validate_project(project)
        # Verify stages
        valid_stages = [s for s in project.workflow.stages if s.stage_type == WorkflowStageType.AGENT]
        agent_stages: dict[str | UUID, AgentStage] = {
            **{s.title: s for s in valid_stages},
            **{s.uuid: s for s in valid_stages},
        }
        self._validate_agent_stages(valid_stages, agent_stages)
        if self.pre_execution_callback:
            self.pre_execution_callback(self)  # type: ignore  [arg-type]
        try:
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
                global_pbar = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TaskSpeedColumn(unit="batches"),
                    TimeElapsedColumn(),
                    transient=True,
                )
                batch_pbar = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TimeElapsedColumn(),
                    TaskSpeedColumn(unit="tasks"),
                    TaskProgressColumn(),
                    transient=True,
                )

                # Information to the formats will be updated in the loop below
                global_task_format = "Executing agent [magenta]`{agent_name}`[/magenta] [cyan](total: {total})"
                batch_task_format = "Executing batch [cyan]{batch_num}[/cyan]"

                # The two tasks that will display the progress
                global_task = global_pbar.add_task(description=global_task_format.format(agent_name="", total=0))
                batch_task = batch_pbar.add_task(description=batch_task_format.format(batch_num=""), total=0)

                # To display two progress bars side at once, we need to create a table
                # and add the two progress bars to it
                progress_table = Table.grid()
                progress_table.add_row(global_pbar)
                progress_table.add_row(batch_pbar)

                for runner_agent in self.agents:
                    include_args = runner_agent.label_row_metadata_include_args or LabelRowMetadataIncludeArgs()
                    init_args = runner_agent.label_row_initialise_labels_args or LabelRowInitialiseLabelsArgs()
                    stage = agent_stages[runner_agent.identity]

                    # Set the progress bar description to display the agent name and total tasks completed
                    global_pbar.update(
                        global_task,
                        description=global_task_format.format(agent_name=runner_agent.printable_name, total=0),
                    )

                    total = 0
                    tasks = stage.get_tasks()
                    batch_size = min(task_batch_size, max_tasks_per_stage) if max_tasks_per_stage else task_batch_size

                    with Live(progress_table, refresh_per_second=1):
                        for batch_num, task_batch in enumerate(batch_iterator(tasks, batch_size)):
                            # Reset the batch progress bar to display the current batch number and total tasks
                            batch_pbar.reset(
                                batch_task,
                                total=len(task_batch),
                                description=batch_task_format.format(batch_num=batch_num),
                            )
                            contexts = self._assemble_contexts(
                                task_batch=task_batch,
                                runner_agent=runner_agent,
                                project=project,
                                include_args=include_args,
                                init_args=init_args,
                                stage=stage,
                                client=self.client,
                            )
                            self._execute_tasks(
                                contexts,
                                runner_agent,
                                stage,
                                num_retries,
                                pbar_update=lambda x: batch_pbar.advance(batch_task, x or 1),
                            )
                            total += len(task_batch)

                            global_pbar.update(
                                global_task,
                                advance=1,
                                description=global_task_format.format(
                                    agent_name=runner_agent.printable_name, total=total
                                ),
                            )
                            if max_tasks_per_stage and total >= max_tasks_per_stage:
                                break

                    global_pbar.stop()
                    batch_pbar.stop()
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

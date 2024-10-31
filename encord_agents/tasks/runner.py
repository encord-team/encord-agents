import time
import traceback
from contextlib import ExitStack
from datetime import datetime, timedelta
from typing import Callable, Iterable, Optional, cast
from uuid import UUID

import rich
from encord.http.bundle import Bundle
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.orm.workflow import WorkflowStageType
from encord.project import Project
from encord.workflow.stages.agent import AgentTask
from encord.workflow.workflow import WorkflowStage
from tqdm.auto import tqdm
from typer import Abort

from encord_agents.core.dependencies.models import Context, DecoratedCallable, Dependant
from encord_agents.core.dependencies.utils import get_dependant, solve_dependencies
from encord_agents.core.utils import get_user_client

TaskAgentReturn = str | UUID | None


class RunnerAgent:
    def __init__(self, identity: str | UUID, callable: Callable[..., TaskAgentReturn]):
        self.name = identity
        self.callable = callable
        self.dependant: Dependant = get_dependant(func=callable)


class Runner:
    """
    Runs agents against Workflow projects.

    When called, it will iteratively run agent stages till they are empty.
    By default, runner will exit after finishing the tasks identified at the point of trigger.
    To automatically re-run, you can use the `refresh_every` keyword.
    """

    @staticmethod
    def verify_project_hash(ph: str) -> str:
        try:
            ph = str(UUID(ph))
        except ValueError:
            print("Could not read project_hash as a UUID")
            raise Abort()
        return ph

    def __init__(self, project_hash: str | None = None):
        self.project_hash = self.verify_project_hash(project_hash) if project_hash else None
        self.client = get_user_client()
        self.project: Project | None = self.client.get_project(self.project_hash) if self.project_hash else None

        self.valid_stages: list[WorkflowStage] | None = None
        if self.project is not None:
            self.valid_stages = [s for s in self.project.workflow.stages if s.stage_type == WorkflowStageType.AGENT]

        self.agents: list[RunnerAgent] = []

    def _add_stage_agent(self, identity: str | UUID, func: Callable[..., TaskAgentReturn]):
        self.agents.append(RunnerAgent(identity=identity, callable=func))

    def stage(self, stage: str | UUID) -> Callable[[DecoratedCallable], DecoratedCallable]:
        if stage in [a.name for a in self.agents]:
            self.abort_with_message(
                f"Stage name [blue]`{stage}`[/blue] has already been assigned a function. You can only assign one callable to each agent stage."
            )

        if self.valid_stages is not None:
            selected_stage: WorkflowStage | None = None
            for v_stage in self.valid_stages:
                attr = v_stage.title if isinstance(stage, str) else v_stage.uuid
                if attr == stage:
                    selected_stage = v_stage

            if selected_stage is None:
                agent_stage_names = ",".join([f"[magenta]`{k}`[/magenta]" for k in self.valid_stages])
                self.abort_with_message(
                    rf"Stage name [blue]`{stage}`[/blue] could not be matched against a project stage. Valid stages are \[{agent_stage_names}]."
                )
            else:
                stage = selected_stage.uuid

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            self._add_stage_agent(stage, func)
            return func

        return decorator

    def _execute_tasks(
        self,
        tasks: Iterable[tuple[AgentTask, LabelRowV2]],
        runner_agent: RunnerAgent,
        # num_threads: int,
        num_retries: int,
        pbar: tqdm | None = None,
    ) -> None:
        project = cast(Project, self.project)
        with Bundle() as bundle:
            for task, label_row in tasks:
                with ExitStack() as stack:
                    context = Context(project=project, task=task, label_row=label_row)
                    dependencies = solve_dependencies(context=context, dependant=runner_agent.dependant, stack=stack)
                    for attempt in range(1, num_retries + 1):
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

                            if pbar is not None:
                                pbar.update(1)
                            break

                        except Exception:
                            print(f"[attempt {attempt}/{num_retries}] Agent failed with error: ")
                            traceback.print_exc()

    @staticmethod
    def abort_with_message(error: str):
        rich.print(error)
        raise Abort()

    def __call__(
        self,
        # num_threads: int = 1,
        refresh_every: int | None = None,
        num_retries: int = 3,
        task_batch_size: int = 300,
        project_hash: Optional[str] = None,
    ):
        """
        Run your task agent.

        The runner can continuously keep looking for new tasks in the project and execute the agent.

        Args:
            refresh_every: Fetch task statuses from the Encord projecet every `refresh_every` seconds.
                If `None`, they the runner will exit once task queue is empty.
            num_retries: If an agent fails on a task, how many times should the runner retry it?
            task_batch_size: Number of tasks for which labels are loaded into memory at once.
            project_hash: the project hash if not defined at runner instantiation.
        Returns:
            None
        """
        # Verify project
        if project_hash is not None:
            project_hash = self.verify_project_hash(project_hash)
            project = self.client.get_project(project_hash)
        else:
            project = self.project

        if project is None:
            self.abort_with_message(
                """Please specify project hash in one of the following ways:  
At instantiation: [blue]`runner = Runner(project_hash="<project_hash>")`[/blue]
or when called: [blue]`runner(project_hash="<project_hash>")`[/blue]
"""
            )
            exit()  ## shouldn't be necessary but pleases pyright

        # Verify stages
        agent_stages: dict[str | UUID, WorkflowStage] = {
            **{s.title: s for s in project.workflow.stages if s.stage_type == WorkflowStageType.AGENT},
            **{s.uuid: s for s in project.workflow.stages if s.stage_type == WorkflowStageType.AGENT},
        }
        for runner_agent in self.agents:
            fn_name = getattr(callable, "__name__", "agent function")
            agent_stage_names = ",".join([f"[magenta]`{k}`[/magenta]" for k in agent_stages.keys()])
            if runner_agent.name not in agent_stages:
                self.abort_with_message(
                    rf"Your function [blue]`{fn_name}`[/blue] was annotated to match agent stage [blue]`{runner_agent.name}`[/blue] but that stage is not present as an agent stage in your project workflow. The workflow has following agent stages : \[{agent_stage_names}]"
                )

            stage = agent_stages[runner_agent.name]
            if stage.stage_type != WorkflowStageType.AGENT:
                self.abort_with_message(
                    f"You cannot use the stage of type `{stage.stage_type}` as an agent stage. It has to be one of the agent stages: [{agent_stage_names}]."
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
                stage = agent_stages[runner_agent.name]

                batch: list[AgentTask] = []
                batch_lrs: list[LabelRowV2] = []

                tasks = list(stage.get_tasks())
                pbar = tqdm(desc="Executing tasks", total=len(tasks))
                for task in tasks:
                    if not isinstance(task, AgentTask):
                        continue
                    batch.append(task)
                    if len(batch) == task_batch_size:
                        label_rows = {
                            UUID(lr.data_hash): lr
                            for lr in project.list_label_rows_v2(data_hashes=[t.data_hash for t in batch])
                        }
                        batch_lrs = [label_rows[t.data_hash] for t in batch]
                        with project.create_bundle() as lr_bundle:
                            for lr in batch_lrs:
                                lr.initialise_labels(bundle=lr_bundle)

                        self._execute_tasks(
                            zip(batch, batch_lrs),
                            runner_agent,
                            num_retries,
                            pbar=pbar,
                        )

                        batch = []
                        batch_lrs = []

                if len(batch) > 0:
                    label_rows = {
                        UUID(lr.data_hash): lr
                        for lr in project.list_label_rows_v2(data_hashes=[t.data_hash for t in batch])
                    }
                    batch_lrs = [label_rows[t.data_hash] for t in batch]
                    with project.create_bundle() as lr_bundle:
                        for lr in batch_lrs:
                            lr.initialise_labels(bundle=lr_bundle)
                    self._execute_tasks(zip(batch, batch_lrs), runner_agent, num_retries, pbar=pbar)

    def run(self):
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

        app = Typer(add_completion=False, rich_markup_mode="rich")
        app.command()(self.__call__)
        app()

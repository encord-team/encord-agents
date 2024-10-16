import time
import traceback
from datetime import datetime, timedelta
from functools import wraps
from types import MappingProxyType
from typing import Callable, Iterable, Literal, Optional, Protocol, Type, TypeVar, overload
from uuid import UUID

import rich
from encord.exceptions import AuthenticationError, AuthorisationError
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.orm.dataset import DatasetAccessSettings
from encord.orm.workflow import WorkflowStageType
from encord.project import Project
from encord.workflow.stages.agent import AgentTask
from typer import Abort

from encord_agents.core.data_model import Frame
from encord_agents.core.utils import download_asset, get_user_client
from encord_agents.core.video import iter_video


class BareAgent(Protocol):
    def __call__(
        self,
        lr: LabelRowV2,
    ) -> str: ...


class MetadataAgent(Protocol):
    def __call__(
        self,
        lr: LabelRowV2,
        metadata: dict | None,
    ) -> str: ...


class IteratorAgent(Protocol):
    def __call__(self, lr: LabelRowV2, *, frames: Iterable[Frame]) -> str: ...


class MetadataIteratorAgent(Protocol):
    def __call__(
        self,
        lr: LabelRowV2,
        *,
        frames: Iterable[Frame],
        metadata: dict | None,
    ) -> str: ...


TaskAgent = BareAgent | MetadataAgent | IteratorAgent | MetadataIteratorAgent

BareWrapper = Callable[[BareAgent], BareAgent]
MetadataWrapper = Callable[[MetadataAgent], MetadataAgent]
IteratorWrapper = Callable[[IteratorAgent], IteratorAgent]
MetadataIteratorWrapper = Callable[[MetadataIteratorAgent], MetadataIteratorAgent]

AgentWrapper = BareWrapper | MetadataWrapper | IteratorWrapper | MetadataIteratorWrapper

TASK_TYPE_LOOKUP: dict[tuple[bool, bool], Type[TaskAgent]] = {
    # (metadata, frame_iter): type
    (False, False): Type[BareAgent],
    (False, True): Type[IteratorAgent],
    (True, False): Type[MetadataAgent],
    (True, True): Type[MetadataIteratorAgent],
}

DecoratedTaskAgent = TypeVar("DecoratedTaskAgent", bound=TaskAgent)


class Runner:
    @staticmethod
    def verify_project_hash(ph: str) -> str:
        try:
            ph = str(UUID(ph))
        except ValueError:
            print("Could not read project_hash as a UUID")
            raise Abort()
        return ph

    def __init__(self, project_hash: str):
        self.project_hash = self.verify_project_hash(project_hash)
        self.client = get_user_client()
        self.project: Project | None = self.client.get_project(self.project_hash) if self.project_hash else None

        self.valid_stage_names: set[str] | None = None
        if self.project is not None:
            self.valid_stage_names = {
                s.title for s in self.project.workflow.stages if s.stage_type == WorkflowStageType.AGENT
            }

        self.agents: dict[str, BareAgent] = {}
        self.agent_types: dict[str, Type[TaskAgent]] = {}

        self.datasets: dict[str, dict[UUID, MappingProxyType | None]] = {}
        """
        Holds dictionaries of <dataset_hash, <data_hash, metadata>> entries.
        """


    @overload
    def stage(self, stage: str, *, metadata: Literal[True], frame_iterator: Literal[True]) -> MetadataIteratorWrapper:
        ...

    @overload
    def stage(self, stage: str, *, metadata: Literal[False], frame_iterator: Literal[True]) -> IteratorWrapper:
        ...

    @overload
    def stage(self, stage: str, *, metadata: Literal[True], frame_iterator: Literal[False]) -> MetadataWrapper:
        ...

    @overload
    def stage(self, stage: str, *, metadata: Literal[False] = False, frame_iterator: Literal[False] = False) -> BareWrapper:
        ...

    def stage(self, stage: str, *, metadata: bool = False, frame_iterator: bool = False) -> AgentWrapper:
        if stage in self.agents:
            self.abort_with_message(
                f"Stage name [blue]`{stage}`[/blue] has already been assigned a function. You can only assign one callable to each agent stage."
            )

        if self.valid_stage_names is not None and stage not in self.valid_stage_names:
            agent_stage_names = ",".join([f"[magenta]`{k}`[/magenta]" for k in self.valid_stage_names])
            self.abort_with_message(
                rf"Stage name [blue]`{stage}`[/blue] could not be matched against a project stage. Valid stages are \[{agent_stage_names}]."
            )

        def context_wrapper_inner(func: DecoratedTaskAgent) -> DecoratedTaskAgent:
            self.agent_types[stage] = TASK_TYPE_LOOKUP[(metadata, frame_iterator)]

            @wraps(func)  # type: ignore
            def wrapper(fn: TaskAgent, lr: LabelRowV2):
                kwargs = {}
                if metadata:
                    kwargs["metadata"] = self.datasets.get(lr.dataset_hash, {}).get(UUID(lr.data_hash))

                if frame_iterator:
                    with download_asset(lr, frame=None) as asset_path:
                        kwargs["frames"] = iter_video(asset_path)
                        return fn(lr, **kwargs)

            self.agents[stage] = wrapper # type: ignore

            return wrapper  # type: ignore

        return context_wrapper_inner

    def _add_dataset_from_label_row(self, lr: LabelRowV2):
        if lr.dataset_hash in self.datasets:
            return

        try:
            dataset = self.client.get_dataset(
                lr.dataset_hash,
                dataset_access_settings=DatasetAccessSettings(fetch_client_metadata=True)
            )
            self.datasets[lr.dataset_hash] = {UUID(dr.uid): dr.client_metadata for dr in dataset.data_rows}

        except (AuthorisationError, AuthenticationError):
                    dataset_title = lr.dataset_title
                    dataset_hash = lr.dataset_hash
                    self.abort_with_message(
                        f"Was not able to access the dataset with [blue]`{dataset_hash=}`[/blue] "
                        f"and [magenta]'{dataset_title=}'[/magenta]. The dataset is needed to be "
                        "able to fetch client metadata. Disable the `metadata` flag or give the "
                        "account access to the dataset.")


    def _execute_tasks(
        self,
        tasks: Iterable[tuple[AgentTask, LabelRowV2]],
        agent: BareAgent,
        num_threads: int,
        num_retries: int,
    ) -> None:
        for task, label_row in tasks:
            for attempt in range(1, num_retries + 1):
                try:
                    next_stage = agent(label_row)  # TODO handle dynamic parameters
                    task.proceed(pathway_name=next_stage)
                except Exception:
                    print(f"[attempt {attempt}/{num_retries}] Agent failed with error: ")
                    traceback.print_exc()

    @staticmethod
    def abort_with_message(error: str):
        rich.print(error)
        raise Abort()

    def __call__(
        self,
        num_threads: int = 1,
        refresh_every: int = 3600,
        num_retries: int = 3,
        task_batch_size: int = 300,
        project_hash: Optional[str] = None,
    ):
        """
        Run your task agent.

        Continuously runs the task agent to keep looking for new tasks in the

        Args:
            num_threads: Number of threads that can run the agent simultaneously.
            refresh_every: Fetch task statuses from the Encord projecet every `refresh_every` seconds.
            num_retries: If an agent fails on a task, how many times should the runner retry it?
            task_batch_size: Number of tasks for which labels are loaded into memory at once.
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
        agent_stages = {s.title: s for s in project.workflow.stages if s.stage_type == WorkflowStageType.AGENT}
        for stage_name, callable in self.agents.items():
            fn_name = getattr(callable, "__name__", "agent function")
            agent_stage_names = ",".join([f"[magenta]`{k}`[/magenta]" for k in agent_stages.keys()])
            if stage_name not in agent_stages:
                self.abort_with_message(
                    rf"Your function [blue]`{fn_name}`[/blue] was annotated to match agent stage [blue]`{stage_name}`[/blue] but that stage is not present as an agent stage in your project workflow. The workflow has following agent stages : \[{agent_stage_names}]"
                )

            __import__('ipdb').set_trace()
            stage = agent_stages[stage_name]
            if stage.stage_type != WorkflowStageType.AGENT:
                self.abort_with_message(
                    f"You cannot use the stage of type `{stage.stage_type}` as an agent stage. It has to be one of the agent stages: [{agent_stage_names}]."
                )

        # Check if we need to initialize datasets
        metadata_stages = {
            k: self.agents[k] for k, t in self.agent_types.items() if t in [MetadataAgent, MetadataIteratorAgent]
        }

        # Run
        delta = timedelta(seconds=refresh_every)
        next_execution = None


        try:
            # TODO do this in background
            while True:
                if next_execution and next_execution > datetime.now():
                    duration = next_execution - datetime.now()
                    print(f"Sleeping {duration.total_seconds()} secs until next execution time.")
                    time.sleep(duration.total_seconds())

                next_execution = datetime.now() + delta
                for stage_name, callable in self.agents.items():
                    stage = agent_stages[stage_name]
                    fetch_metadata = stage.title in metadata_stages

                    batch: list[AgentTask] = []
                    for task in stage.get_tasks():
                        batch.append(task)

                        if len(batch) == task_batch_size:
                            label_rows = {
                                UUID(lr.data_hash): lr
                                for lr in project.list_label_rows_v2(data_hashes=[t.data_hash for t in batch])
                            }
                            batch_lrs = [label_rows[t.data_hash] for t in batch]
                            with project.create_bundle() as bundle:
                                for lr in batch_lrs:
                                    lr.initialise_labels(bundle=bundle)
                                    if fetch_metadata and lr.dataset_hash not in self.datasets:
                                        self._add_dataset_from_label_row(lr)                            

                            self._execute_tasks(
                                zip(batch, batch_lrs),
                                callable,
                                num_threads,
                                num_retries,
                            )

                    if len(batch) > 0:
                        label_rows = {
                            UUID(lr.data_hash): lr
                            for lr in project.list_label_rows_v2(data_hashes=[t.data_hash for t in batch])
                        }
                        batch_lrs = [label_rows[t.data_hash] for t in batch]
                        with project.create_bundle() as bundle:
                            for lr in batch_lrs:
                                lr.initialise_labels(bundle=bundle)
                                if fetch_metadata and lr.dataset_hash not in self.datasets:
                                    self._add_dataset_from_label_row(lr)                            
                        self._execute_tasks(zip(batch, batch_lrs), callable, num_threads, num_retries)

        except KeyboardInterrupt:
            # TODO run thread until end, then stop
            exit()


if __name__ == "__main__":
    # TODO remove me
    project_hash = "2400d7dd-0be2-40fb-bca7-5f58db5b70d3"
    runner = Runner(project_hash=project_hash)

    @runner.stage(stage="pre-label")
    def run_something(lr: LabelRowV2):
        print(lr.data_title)
        #print(metadata)
        #for frame in frames:
        #print(frame.content.shape)
        #break
        return "annotate"

    from typer import Typer

    app = Typer(add_completion=False, rich_markup_mode="rich")
    app.command()(runner.__call__)
    app()

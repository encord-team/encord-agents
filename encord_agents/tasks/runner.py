import inspect
import time
import traceback
from contextlib import ExitStack, contextmanager
from copy import copy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, ForwardRef, Iterable, Iterator, Optional, TypeVar, cast
from uuid import UUID

import rich
from encord.exceptions import InvalidArgumentsError
from encord.http.bundle import Bundle
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.orm.workflow import WorkflowStageType
from encord.project import Project
from encord.workflow.stages.agent import AgentTask
from pydantic._internal._typing_extra import eval_type_lenient as evaluate_forwardref
from tqdm.auto import tqdm
from typer import Abort
from typing_extensions import Annotated, get_args, get_origin

from encord_agents.core.utils import get_user_client

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., Any])

class Depends:
    def __init__(
        self, dependency: Optional[Callable[..., Any]] = None
    ):
        self.dependency = dependency

    def __repr__(self) -> str:
        attr = getattr(self.dependency, "__name__", type(self.dependency).__name__)
        return f"{self.__class__.__name__}({attr})"

@dataclass
class _Field:
    name: str
    type_annotation: Any

@dataclass
class Dependant:
    name: Optional[str] = None
    func: Optional[Callable[..., Any]] = None
    dependencies: list["Dependant"] = field(default_factory=list)
    field_params: list[_Field] = field(default_factory=list)
    needs_label_row: bool = False


@dataclass
class ParamDetails:
    type_annotation: Any
    depends: Optional[Depends]


class RunnerAgent:
    def __init__(self, name: str, callable: Callable[..., str]):
        self.name = name
        self.callable = callable
        self.dependant: Dependant = get_dependant(func=callable)


def get_typed_annotation(annotation: Any, globalns: dict[str, Any]) -> Any:
    if isinstance(annotation, str):
        annotation = ForwardRef(annotation)
        annotation = evaluate_forwardref(annotation, globalns, globalns)
    return annotation


def get_typed_signature(call: Callable[..., Any]) -> inspect.Signature:
    signature = inspect.signature(call)
    globalns = getattr(call, "__globals__", {})
    typed_params = [
        inspect.Parameter(
            name=param.name,
            kind=param.kind,
            default=param.default,
            annotation=get_typed_annotation(param.annotation, globalns),
        )
        for param in signature.parameters.values()
    ]
    typed_signature = inspect.Signature(typed_params)
    return typed_signature

def get_dependant(
    *,
    func: Callable[..., Any],
    name: Optional[str] = None,
) -> Dependant:
    endpoint_signature = get_typed_signature(func)
    signature_params = endpoint_signature.parameters
    dependant = Dependant(
        func=func,
        name=name,
    )
    for param_name, param in signature_params.items():
        param_details = analyze_param(
            param_name=param_name,
            annotation=param.annotation,
            value=param.default,
        )
        if param_details.depends is not None:
            sub_dependant = get_param_sub_dependant(
                param_name=param_name,
                depends=param_details.depends,
            )
            dependant.dependencies.append(sub_dependant)
        else:
            dependant.field_params.append(_Field(name=param_name, type_annotation=param_details.type_annotation))

    return dependant



def get_param_sub_dependant(
    *,
    param_name: str,
    depends: Depends,
) -> Dependant:
    assert depends.dependency
    return get_sub_dependant(
        dependency=depends.dependency,
        name=param_name,
    )


def get_sub_dependant(
    *,
    dependency: Callable[..., Any],
    name: Optional[str] = None,
) -> Dependant:
    sub_dependant = get_dependant(
        func=dependency,
        name=name,
    )
    return sub_dependant


def analyze_param(
    *,
    param_name: str,
    annotation: Any,
    value: Any,
) -> ParamDetails:
    depends = None
    type_annotation: Any = Any
    use_annotation: Any = Any
    if annotation is not inspect.Signature.empty:
        use_annotation = annotation
        type_annotation = annotation
    # Extract Annotated info
    origin = get_origin(use_annotation)
    if origin is Annotated:
        annotated_args = get_args(annotation)
        type_annotation = annotated_args[0]
        dependency_args = [
            arg
            for arg in annotated_args[1:]
            if isinstance(arg, Depends)
        ]
        if dependency_args:
            agent_annotation: Depends | None = (
                dependency_args[-1]
            )
        else:
            agent_annotation = None

        if isinstance(agent_annotation, Depends):
            depends = agent_annotation
    elif annotation is LabelRowV2 or annotation is AgentTask:
        return ParamDetails(type_annotation=annotation, depends=None)


    # Get Depends from default value
    if isinstance(value, Depends):
        assert depends is None, (
            "Cannot specify `Depends` in `Annotated` and default value"
            f" together for {param_name!r}"
        )
        depends = value

    # Get Depends from type annotation
    if depends is not None and depends.dependency is None:
        # Copy `depends` before mutating it
        depends = copy(depends)
        depends.dependency = type_annotation

    return ParamDetails(type_annotation=type_annotation, depends=depends)


@dataclass
class SolvedDependency:
    values: dict[str, Any]
    dependency_cache: Optional[dict[Callable[..., Any], Any]] = None


def is_gen_callable(call: Callable[..., Any]) -> bool:
    if inspect.isgeneratorfunction(call):
        return True
    dunder_call = getattr(call, "__call__", None)  # noqa: B004
    return inspect.isgeneratorfunction(dunder_call)


def solve_generator(
    *, call: Callable[..., Any], stack: ExitStack, sub_values: dict[str, Any]
) -> Any:
    cm = contextmanager(call)(**sub_values)
    return stack.enter_context(cm)


def get_field_values(deps: list[_Field], agent_task: AgentTask, label_row: LabelRowV2) -> dict[str, AgentTask | LabelRowV2]:
    values: dict[str, AgentTask | LabelRowV2] = {}
    for param_field in deps:
        if param_field.type_annotation is AgentTask:
            values[param_field.name] = agent_task
        elif param_field.type_annotation is LabelRowV2:
            values[param_field.name] = label_row
        else:
            raise ValueError(f"Agent function is specifying a field `{param_field.name} ({param_field.type_annotation})` which is not supported. Consider wrapping it in a `Depends` to define how this value should be obtained.")
    return values

def solve_dependencies(
    *,
    agent_task: AgentTask,
    label_row: LabelRowV2,
    dependant: Dependant,
    stack: ExitStack,
    dependency_cache: Optional[dict[Callable[..., Any], Any]] = None
) -> SolvedDependency:
    values: dict[str, Any] = {}
    dependency_cache = dependency_cache or {}
    sub_dependant: Dependant
    for sub_dependant in dependant.dependencies:
        sub_dependant.func = cast(Callable[..., Any], sub_dependant.func)
        func = sub_dependant.func
        use_sub_dependant = sub_dependant

        solved_result = solve_dependencies(
            agent_task=agent_task,
            label_row=label_row,
            dependant=use_sub_dependant,
            stack=stack,
            dependency_cache=dependency_cache,
        )

        dependency_cache.update(solved_result.dependency_cache or {})

        if sub_dependant.func in dependency_cache:
            solved = dependency_cache[sub_dependant.func]
        elif is_gen_callable(func):
            solved = solve_generator(
                call=func, stack=stack, sub_values=solved_result.values
            )
        else:
            solved = func(**solved_result.values)

        if sub_dependant.name is not None:
            values[sub_dependant.name] = solved

    field_values = get_field_values(dependant.field_params, agent_task, label_row)
    values.update(field_values)

    return SolvedDependency(
        values=values,
        dependency_cache=dependency_cache,
    )


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

        self.agents: list[RunnerAgent] = []

    def _add_stage_agent(self, name: str, func: Callable[..., Any]):
        self.agents.append(RunnerAgent(name=name, callable=func))



    def stage(self, stage: str) -> Callable[[DecoratedCallable], DecoratedCallable]:
        if stage in [a.name for a in self.agents]:
            self.abort_with_message(
                f"Stage name [blue]`{stage}`[/blue] has already been assigned a function. You can only assign one callable to each agent stage."
            )

        if self.valid_stage_names is not None and stage not in self.valid_stage_names:
            agent_stage_names = ",".join([f"[magenta]`{k}`[/magenta]" for k in self.valid_stage_names])
            self.abort_with_message(
                rf"Stage name [blue]`{stage}`[/blue] could not be matched against a project stage. Valid stages are \[{agent_stage_names}]."
            )

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
        pbar: tqdm | None = None
    ) -> None:
        with Bundle() as bundle:
            for task, label_row in tasks:
                with ExitStack() as stack:
                    for attempt in range(1, num_retries + 1):
                        try:
                            dependencies = solve_dependencies(agent_task=task, label_row=label_row, dependant=runner_agent.dependant, stack=stack)
                            next_stage = runner_agent.callable(**dependencies.values)  
                            try:
                                task.proceed(pathway_name=next_stage, bundle=bundle)
                                if pbar is not None:
                                    pbar.update(1)
                                break
                            except InvalidArgumentsError as e:
                                print(e)
                                traceback.print_exc()
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
                for runner_agent in self.agents:
                    stage = agent_stages[runner_agent.name]

                    batch: list[AgentTask] = []
                    batch_lrs: list[LabelRowV2] = []

                    tasks = list(stage.get_tasks())
                    pbar = tqdm(desc="Executing tasks", total=len(tasks))
                    for task in tasks:
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

        except KeyboardInterrupt:
            # TODO run thread until end, then stop
            exit()



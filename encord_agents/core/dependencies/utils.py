import inspect
from contextlib import ExitStack, contextmanager
from copy import copy
from dataclasses import dataclass
from typing import Any, Callable, ForwardRef, Optional, cast

from encord.objects.ontology_labels_impl import LabelRowV2
from encord.project import Project
from encord.workflow.stages.agent import AgentTask
from pydantic._internal._typing_extra import eval_type_lenient as evaluate_forwardref
from typing_extensions import Annotated, get_args, get_origin

from encord_agents.core.data_model import FrameData
from encord_agents.core.dependencies.models import Context, Dependant, Depends, ParamDetails, _Field


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
            dependant.needs_label_row |= sub_dependant.needs_label_row
        else:
            dependant.field_params.append(_Field(name=param_name, type_annotation=param_details.type_annotation))
            dependant.needs_label_row |= param_details.type_annotation is LabelRowV2

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
        dependency_args = [arg for arg in annotated_args[1:] if isinstance(arg, Depends)]
        if dependency_args:
            agent_annotation: Depends | None = dependency_args[-1]
        else:
            agent_annotation = None

        if isinstance(agent_annotation, Depends):
            depends = agent_annotation
    elif annotation is LabelRowV2 or annotation is AgentTask or annotation is FrameData:
        return ParamDetails(type_annotation=annotation, depends=None)

    # Get Depends from default value
    if isinstance(value, Depends):
        assert depends is None, (
            "Cannot specify `Depends` in `Annotated` and default value" f" together for {param_name!r}"
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


def solve_generator(*, call: Callable[..., Any], stack: ExitStack, sub_values: dict[str, Any]) -> Any:
    cm = contextmanager(call)(**sub_values)
    return stack.enter_context(cm)


def get_field_values(deps: list[_Field], context: Context) -> dict[str, AgentTask | LabelRowV2 | Project | FrameData]:
    values: dict[str, AgentTask | LabelRowV2 | Project | FrameData] = {}
    for param_field in deps:
        if param_field.type_annotation is FrameData:
            if context.frame_data is None:
                raise ValueError(
                    "It looks like you're trying to access `frame_data` from a task agent. That is not supported, as task agents are not triggered from specific frames."
                )
            values[param_field.name] = context.frame_data
        elif param_field.type_annotation is AgentTask:
            if context.task is None:
                raise ValueError(
                    "It looks like you're trying to access an agent task from an editor agent. That is not supported, as editor agents are not associated with tasks."
                )
            values[param_field.name] = context.task
        elif param_field.type_annotation is LabelRowV2:
            if context.label_row is None:
                raise ValueError(
                    "Failed to parse dependency tree correctly. Context should have had a label row. Please contact support@encord.com with as much detail as you can (stacktrace, dependency, function declaration)"
                )
            values[param_field.name] = context.label_row
        elif param_field.type_annotation is Project:
            values[param_field.name] = context.project
        else:
            raise ValueError(
                f"Agent function is specifying a field `{param_field.name}` with type `{param_field.type_annotation}` "
                "which is not supported. Consider wrapping it in a `encord_agents.core.dependencies.Depends` to define "
                "how this value should be obtained. More info here: `https://agents-docs.encord.com/dependencies`"
            )
    return values


def solve_dependencies(
    *,
    context: Context,
    dependant: Dependant,
    stack: ExitStack,
    dependency_cache: Optional[dict[Callable[..., Any], Any]] = None,
) -> SolvedDependency:
    values: dict[str, Any] = {}
    dependency_cache = dependency_cache or {}
    sub_dependant: Dependant
    for sub_dependant in dependant.dependencies:
        sub_dependant.func = cast(Callable[..., Any], sub_dependant.func)
        func = sub_dependant.func
        use_sub_dependant = sub_dependant

        solved_result = solve_dependencies(
            context=context,
            dependant=use_sub_dependant,
            stack=stack,
            dependency_cache=dependency_cache,
        )

        dependency_cache.update(solved_result.dependency_cache or {})

        if sub_dependant.func in dependency_cache:
            solved = dependency_cache[sub_dependant.func]
        elif is_gen_callable(func):
            solved = solve_generator(call=func, stack=stack, sub_values=solved_result.values)
        else:
            solved = func(**solved_result.values)

        if sub_dependant.name is not None:
            values[sub_dependant.name] = solved

    field_values = get_field_values(dependant.field_params, context)
    values.update(field_values)

    return SolvedDependency(
        values=values,
        dependency_cache=dependency_cache,
    )

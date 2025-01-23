from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar
from uuid import UUID

from encord.objects.ontology_labels_impl import LabelRowV2
from encord.project import Project
from encord.workflow.stages.agent import AgentTask

from encord_agents.core.data_model import FrameData

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., str | UUID | None])


class Depends:
    def __init__(self, dependency: Optional[Callable[..., Any]] = None):
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
class Context:
    project: Project
    label_row: LabelRowV2 | None
    task: AgentTask | None = None
    frame_data: FrameData | None = None


@dataclass
class ParamDetails:
    type_annotation: Any
    depends: Optional[Depends]

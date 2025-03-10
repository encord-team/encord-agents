import os
from contextlib import ExitStack
from typing import Generator, NamedTuple

import pytest
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.project import Project
from encord.storage import StorageItem
from encord.user_client import EncordUserClient
from typing_extensions import Annotated

from encord_agents.core.dependencies.models import Context, Depends
from encord_agents.core.dependencies.utils import get_dependant, solve_dependencies


class SharedResolutionContext(NamedTuple):
    project: Project
    first_label_row: LabelRowV2
    storage_item: StorageItem


# Load project info once for the class
@pytest.fixture(scope="class")
def context(user_client: EncordUserClient, class_level_ephemeral_project_hash: str) -> SharedResolutionContext:
    project = user_client.get_project(class_level_ephemeral_project_hash)
    first_label_row = project.list_label_rows_v2()[0]
    storage_item = user_client.get_storage_item(first_label_row.backing_item_uuid or "")
    return SharedResolutionContext(project=project, first_label_row=first_label_row, storage_item=storage_item)


class TestDependencyResolution:
    project: Project
    first_label_row: LabelRowV2
    storage_item: StorageItem

    # Set the project and first label row for the class
    @classmethod
    @pytest.fixture(autouse=True)
    def setup(cls, context: SharedResolutionContext) -> None:
        cls.project = context.project
        cls.first_label_row = context.first_label_row
        cls.storage_item = context.storage_item

    def test_resolve_flat(self) -> None:
        def dependency1() -> str:
            """
            Annotated dependency
            """
            return "dependency value 1"

        def dependency2() -> Generator[dict[str, str], None, None]:
            """
            Annotated dependency as generator.
            """
            some_object = {"test": "value"}
            yield some_object
            assert "new_key" in some_object

        def func1(
            project: Project,
            label_row: LabelRowV2,
            annotated_dependency: Annotated[str, Depends(dependency1)],
            generator_dependency: Annotated[dict[str, str], Depends(dependency2)],
        ) -> None:
            # Test that dependencies are resolved via context
            assert project.title
            assert label_row.data_title is not None
            assert self.project == project

            # Test that dependencies are resolved via annotated dependencies
            assert annotated_dependency == "dependency value 1"

            # Test that dependencies are resolved via annotated generator dependencies
            # assign new key to dict (asserted in dependency2 that it exists after function ends)
            assert "test" in generator_dependency
            assert "new_key" not in generator_dependency
            generator_dependency["new_key"] = "new_value"

        dependant = get_dependant(
            name="func1",
            func=func1,
        )
        assert dependant.name == "func1"
        assert dependant.func == func1
        assert len(dependant.dependencies) == 2
        assert len(dependant.field_params) == 2

        with ExitStack() as stack:
            context = Context(project=self.project, label_row=self.first_label_row)
            dependencies = solve_dependencies(context=context, dependant=dependant, stack=stack)
            func1(**dependencies.values)

    def test_resolve_nested(self) -> None:
        str_format = "test_resolve_nested_{}"

        def child_dependency(label_row: LabelRowV2) -> str:
            return label_row.data_title

        def parent_dependency(child_dependency: Annotated[str, Depends(child_dependency)]) -> str:
            return str_format.format(child_dependency)

        def func1(
            label_row: LabelRowV2,
            parent_value: Annotated[str, Depends(parent_dependency)],
        ) -> None:
            assert parent_value == str_format.format(label_row.data_title)

        dependant = get_dependant(
            name="func1",
            func=func1,
        )
        with ExitStack() as stack:
            context = Context(project=self.project, label_row=self.first_label_row)
            dependencies = solve_dependencies(context=context, dependant=dependant, stack=stack)
            func1(**dependencies.values)

    def test_resolve_shared_resources(self) -> None:
        """
        Test that shared resources are resolved correctly.
        If the dict of the shared resource is modified in one dependency,
        it should be reflected in the other dependency.
        """

        def shared_resource_dependency() -> dict[str, str]:
            return {}

        def dependency1(
            shared_resource: Annotated[dict[str, str], Depends(shared_resource_dependency)],
        ) -> dict[str, str]:
            shared_resource["test1"] = "value1"
            return shared_resource

        def dependency2(
            shared_resource: Annotated[dict[str, str], Depends(shared_resource_dependency)],
        ) -> dict[str, str]:
            shared_resource["test2"] = "value2"
            return shared_resource

        def func1(
            dep1: Annotated[dict[str, str], Depends(dependency1)],
            dep2: Annotated[dict[str, str], Depends(dependency2)],
        ) -> None:
            assert "test1" in dep2
            assert "test2" in dep1
            assert dep1 == dep2

        dependant = get_dependant(name="func1", func=func1)

        with ExitStack() as stack:
            context = Context(project=self.project, label_row=self.first_label_row)
            dependencies = solve_dependencies(context=context, dependant=dependant, stack=stack)
            func1(**dependencies.values)

    def test_depends_repr(self) -> None:
        def func2() -> int:
            return 1

        def func1(
            dep1: Annotated[int, Depends(func2)],
        ) -> None:
            assert dep1 == 1

        dep = Depends(func1)
        out = dep.__repr__()
        assert out == "Depends(func1)"

    def test_string_annotation_forward_ref(self) -> None:
        def func1(
            project: "Project",
        ) -> None:
            # Test that dependencies are resolved via context
            assert project == self.project

        dependant = get_dependant(
            name="func1",
            func=func1,
        )
        with ExitStack() as stack:
            context = Context(project=self.project, label_row=self.first_label_row)
            dependencies = solve_dependencies(context=context, dependant=dependant, stack=stack)
            func1(**dependencies.values)

    @staticmethod
    def test_label_row_dependency() -> None:
        def func1(
            label_row: LabelRowV2,
        ) -> None:
            assert label_row.data_title is not None

        dependant = get_dependant(name="func1", func=func1)
        assert dependant.needs_label_row

        def func2(
            project: Project,
        ) -> None: ...

        dependant = get_dependant(name="func2", func=func2)
        assert not dependant.needs_label_row

        def dep1(label_row: LabelRowV2) -> str:
            return label_row.data_title

        def func3(
            dep1: Annotated[str, Depends(dep1)],
        ) -> None:
            assert dep1

        dependant = get_dependant(name="func3", func=func3)
        assert dependant.needs_label_row

    @staticmethod
    def test_storage_item_dependency() -> None:
        def func1(
            storage_item: StorageItem,
        ) -> None:
            assert storage_item.name is not None

        dependant = get_dependant(name="func1", func=func1)
        assert dependant.needs_storage_item

        def func2(
            project: Project,
        ) -> None: ...

        dependant = get_dependant(name="func2", func=func2)
        assert not dependant.needs_storage_item

        def dep1(storage_item: StorageItem) -> str:
            return storage_item.name

        def func3(
            dep1: Annotated[str, Depends(dep1)],
        ) -> None:
            assert dep1

        dependant = get_dependant(name="func3", func=func3)
        assert dependant.needs_storage_item

    @staticmethod
    def test_dont_use_annotated_and_default_value_dependencies_together() -> None:
        def dep1_fn() -> str:
            return "value1"

        def func1(dep1: Annotated[str, Depends(dep1_fn)] = Depends(dep1_fn)) -> None: ...  # type: ignore[assignment]

        with pytest.raises(AssertionError) as e:
            get_dependant(name="func1", func=func1)

        assert "Cannot specify `Depends` in `Annotated` and default value" in str(e.value)

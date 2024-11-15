import json
from enum import Enum
from typing import Any, ClassVar, Generic, Literal, TypeVar, Union, cast, overload

from encord.objects.attributes import (
    Attribute,
    ChecklistAttribute,
    RadioAttribute,
    TextAttribute,
)
from encord.objects.classification import Classification
from encord.objects.classification_instance import ClassificationInstance
from encord.objects.common import Shape
from encord.objects.ontology_object import Object
from encord.objects.ontology_object_instance import ObjectInstance
from encord.objects.ontology_structure import OntologyStructure
from encord.objects.options import NestableOption
from encord.objects.utils import _lower_snake_case as lower_snake_case
from pydantic import BaseModel, Field, create_model

KEEP_CHARS = {"_", " "}
OBJECTS_RADIO_MODEL = "ObjectsRadioModel"


# === UTILITY FUNCTIONS === #
def safe_str(unsafe: str) -> str:
    if not isinstance(unsafe, str):
        raise ValueError(f"{unsafe} ({type(unsafe)}) not a string")
    return "".join(c for c in unsafe if c.isalnum() or c in KEEP_CHARS).strip()


def safe_str_camel(unsafe: str) -> str:
    return safe_str(unsafe).title().replace(" ", "").replace("_", "")


def safe_key(unsafe: str) -> str:
    res = safe_str(unsafe).replace(" ", "_")
    return res


# === Pydantic Dynamic models === #
class GenericFieldModel(BaseModel):
    feature_node_hash: str = Field()

    def set_answer(self, instance: ClassificationInstance) -> None:
        """
        This function will be called from the parsing loop to allow the model to set it self as answer
        on the classification instance.
        """
        ...


class GenericRadioModel(GenericFieldModel):
    is_flat: ClassVar[bool]


FieldType = Any
"""
Field from pydantic can be anything so hard to type. This is supposed to indicate that you should use the
`pydantic.Field` function to construct this var.
"""

TypeFieldDefinition = tuple[GenericFieldModel, FieldType]


def create_text_field(attr: TextAttribute) -> TypeFieldDefinition:
    text_field = Field(
        min_length=0,
        max_length=1000,
        description=f"Please describe the image as accurate as possible focusing on '{attr.name}'",
    )
    TextModel = create_model(
        f"{safe_str_camel(attr.title)}TextModel",
        __base__=GenericFieldModel,
        feature_node_hash=(
            Literal[attr.feature_node_hash],
            Field(description="UUID for discrimination. Must be included in json as is."),
        ),  # type: ignore
        **{"value": (str, text_field)},  # type: ignore
    )

    def set_answer(self, instance: ClassificationInstance):
        instance.set_answer(self.value, attribute=attr)

    TextModel.set_answer = set_answer

    return TextModel, Field(
        description="A text attribute with carefully crafted text to describe the property.",
    )


def create_checkbox_field(
    attr: ChecklistAttribute,
) -> TypeFieldDefinition:
    options = [o for o in attr.options]  # shallow copy here.
    ChecklistModel = create_model(
        f"{safe_str_camel(attr.title)}ChecklistModel",
        __base__=GenericFieldModel,
        feature_node_hash=(
            Literal[attr.feature_node_hash],
            Field(description="UUID for discrimination. Must be included in json as is."),
        ),  # type: ignore
        **{
            safe_key(o.value): (
                bool,
                Field(description=f"Is '{o.title}' applicable or not?"),
            )
            for o in options
        },  # type: ignore
    )

    def set_answer(self, instance: ClassificationInstance) -> None:
        choices = [o for o, a in zip([None] + options, vars(self).values()) if a and o]
        instance.set_answer(choices, attribute=attr)

    ChecklistModel.set_answer = set_answer

    return (
        ChecklistModel,
        Field(
            description="A collection of boolean values indicating which concepts are applicable according to the image content."
        ),
    )


def create_radio_field(
    attr: RadioAttribute,
) -> TypeFieldDefinition:
    options = [o for o in attr.options]  # shallow copy here.
    is_flat = all([len(o.attributes) == 0 for o in options])

    options_union: Any = None
    option_lookup: dict[Any, NestableOption] = {}
    if is_flat:
        legal_objects = [o for o in options if not o.attributes]
        FlatOptionModel = Enum(  # < becomes radio model
            f"{safe_str_camel(attr.title)}RadioEnum",
            {safe_key(o.value): o.title for o in legal_objects},
        )
        options_union = FlatOptionModel
        option_lookup.update(
            {FlatOptionModel.__members__[safe_key(o.value)]: o for o in legal_objects}  # type: ignore
        )  # type: ignore
    else:
        for option in options:
            if option.attributes:
                fields = dict([construct_fields(attr) for attr in option.attributes])

                def set_nested_answer(self, ins):
                    for attr_key, attr_val in vars(self).items():
                        if attr_key == "feature_node_hash":
                            continue
                        attr_val.set_answer(ins)
            else:
                fields = {
                    "title": (Literal[safe_str(option.label)], Field("Constant value - should be included as-is."))
                }  # type:ignore

                def set_nested_answer(self, ins):
                    pass

            NestedModel = create_model(
                f"{safe_str_camel(option.value)}NestedRadioModel",
                __base__=GenericRadioModel,
                feature_node_hash=(
                    Literal[option.feature_node_hash],
                    Field(description="UUID for discrimination. Must be included in json as is."),
                ),  # type: ignore
                **fields,  # type: ignore
            )

            NestedModel.set_answer = set_nested_answer
            options_union = Union[options_union, NestedModel] if options_union is not None else NestedModel
            option_lookup[NestedModel] = option

    field_options: dict[str, Any] = {} if is_flat else {"discriminator": "feature_node_hash"}
    RadioModel = create_model(
        f"{safe_str_camel(attr.title)}RadioModel",
        __base__=GenericRadioModel,
        feature_node_hash=(
            Literal[attr.feature_node_hash],
            Field(description="UUID for discrimination. Must be included in json as is."),
        ),  # type: ignore
        is_flat=is_flat,
        **{
            "choice": (
                options_union,
                Field(description="Choose exactly one answer from the given options.", **field_options),
            )
        },  # type: ignore
    )

    def set_answer(self, ins: ClassificationInstance) -> None:
        key = self.choice if isinstance(self.choice, Enum) else type(self.choice)
        ont_option = option_lookup[key]
        ins.set_answer(ont_option, attribute=attr)
        if isinstance(self.choice, GenericFieldModel):
            self.choice.set_answer(ins)

    RadioModel.set_answer = set_answer

    return (
        RadioModel,
        Field(
            description="A mutually exclusive radio attribute to choose exactly one option that best matches to the give visual input."
        ),
    )


def construct_fields(attr: Attribute) -> tuple[str, TypeFieldDefinition]:
    field_name = lower_snake_case(safe_str(attr.title))

    if isinstance(attr, TextAttribute):
        field = create_text_field(attr)
    elif isinstance(attr, ChecklistAttribute):
        field = create_checkbox_field(attr)
    elif isinstance(attr, RadioAttribute):
        field = create_radio_field(attr)
    else:
        raise NotImplementedError(f"Don't know this type of attribute {attr}")
    return field_name, field


def create_objects_model(
    objects: list[Object],
) -> BaseModel:
    is_flat = all([len(o.attributes) == 0 for o in objects])

    objects_union: Any = None
    object_lookup: dict[Any, Object] = {}
    if is_flat:
        legal_objects = [o for o in objects if not o.attributes]
        FlatOptionModel = Enum(  # < becomes radio model
            "ObjectEnumOptions",
            {safe_key(o.title): o.title for o in legal_objects},
        )
        objects_union = FlatOptionModel
        object_lookup.update(
            {FlatOptionModel.__members__[safe_key(o.title)]: o for o in legal_objects}  # type: ignore
        )  # type: ignore
    else:
        for object in objects:
            if object.attributes:
                fields = dict([construct_fields(attr) for attr in object.attributes])

                def set_nested_answer(self, ins):
                    for attr_key, attr_val in vars(self).items():
                        if attr_key == "feature_node_hash":
                            continue
                        attr_val.set_answer(ins)

            else:
                fields = {
                    "title": (Literal[safe_str(object.title)], Field("Constant value - should be included as-is."))
                }  # type:ignore

                def set_nested_answer(self, ins):
                    pass

            fields = dict([construct_fields(attr) for attr in object.attributes])
            NestedModel = create_model(
                f"{safe_str_camel(object.title)}NestedModel",
                __base__=GenericRadioModel,
                feature_node_hash=(
                    Literal[object.feature_node_hash],
                    Field(description="UUID for discrimination. Must be included in json as is."),
                ),  # type: ignore
                **fields,  # type: ignore
            )

            NestedModel.set_answer = set_nested_answer
            objects_union = Union[objects_union, NestedModel] if objects_union is not None else NestedModel
            object_lookup[NestedModel] = object

    field_options: dict[str, Any] = {} if is_flat else {"discriminator": "feature_node_hash"}
    ObjectsRadioModel = create_model(
        OBJECTS_RADIO_MODEL,
        is_flat=(ClassVar[bool], is_flat),
        **{
            "choice": (
                objects_union,
                Field(description="Choose exactly one answer from the given options.", **field_options),
            )
        },  # type: ignore
    )

    def get_ontology_object(self):
        key = self.choice if isinstance(self.choice, Enum) else type(self.choice)
        return object_lookup[key]

    ObjectsRadioModel.get_ontology_object = get_ontology_object
    return ObjectsRadioModel


OntologyType = TypeVar("OntologyType", bound=Classification | Object)


class OntologyDataModel(Generic[OntologyType]):
    """
    Class to create a pydantic model equivalent to an arbitrary classification ontology.

    The model can be used to form a json schema based on the ontology. This is useful if
    you are, e.g., trying to get a structured respone from an LLM.

    **Example:**

    ```python
    from pydantic import ValidationError

    classifications = project.ontology_structure.classifications
    objects = project.ontology_structure.classifications

    data_model = OntologyDataModel([objects])
    # or
    data_model = OntologyDataModel([classifications])

    # Get a json schema for the ontology
    print(data_model.model_json_schema_str)

    # Parse json following the schema into label instances
    json_str = my_favourite_llm(
        f"what is this? pls follow {schema}", img
    )
    try:
        instances = data_model(json_str)
    except ValidationError:
        # invalid json
        ...

    for ins in instances:
        label_row.add_classification_instance(ins)

    label_row.save()
    ```

    For a concrete example, please see [](TODO)

    Attributes:
        ontology:
        DataModel:
    """

    def __init__(self, root_obj: list[OntologyType] | OntologyType):
        _root_obj: list[OntologyType]
        if isinstance(root_obj, list):
            assert len(root_obj) != 0, "No ontology objects given to transform into a pydantic model"
            first, *rest = root_obj
            assert all(
                (isinstance(r, type(first)) for r in rest)
            ), "You cannot mix classifications and objects in the same model"
            _root_obj = root_obj
        else:
            _root_obj = [root_obj]

        self.ontology_lookup: dict[str, OntologyType] = {
            a.feature_node_hash: r for r in _root_obj for a in r.attributes
        }
        self.DataModel: BaseModel
        if isinstance(_root_obj[0], Object):
            legal_shapes = {Shape.BOUNDING_BOX, Shape.BITMASK, Shape.POLYGON, Shape.ROTATABLE_BOUNDING_BOX}

            illegal_objects = [o for o in _root_obj if o.shape not in legal_shapes]  # type: ignore

            if illegal_objects:
                illegal_names = [f'Object(name="{o.name}", shape={o.shape})' for o in illegal_objects]  # type: ignore
                assert not illegal_objects, f"Illegal shapes in provided ontology objects: `{illegal_names}`"

            self.DataModel = create_objects_model(_root_obj)  # type: ignore

        else:
            # Classifications can be build into one
            classification_fields = dict([construct_fields(attr) for clf in _root_obj for attr in clf.attributes])
            self.DataModel: BaseModel = create_model("ClassificationModel", **classification_fields)  # type: ignore

    @property
    def model_json_schema(self) -> dict[str, Any]:
        return self.DataModel.model_json_schema()

    @property
    def model_json_schema_str(self) -> str:
        return json.dumps(self.model_json_schema)

    @overload
    def __call__(self: "OntologyDataModel[Classification]", answer: str) -> list[ClassificationInstance]: ...

    @overload
    def __call__(self: "OntologyDataModel[Object]", answer: str) -> ObjectInstance: ...

    def __call__(
        self: "OntologyDataModel[Classification] | OntologyDataModel[Object]", answer: str
    ) -> list[ClassificationInstance] | ObjectInstance:
        """
        Validate a json response in accordance to the pydantic model.

        This function allows you to convert from a json object (e.g., coming from an llm)
        back to the encord "instance format".

        Args:
            answer_str: The json object as a raw string.

        Returns: a list of classification / object instances that you will then
            have to add to a label row.

        """
        return self.validate_json(answer)

    @overload
    def validate_json(self: "OntologyDataModel[Classification]", answer_str: str) -> list[ClassificationInstance]: ...

    @overload
    def validate_json(self: "OntologyDataModel[Object]", answer_str: str) -> ObjectInstance: ...

    def validate_json(
        self: "OntologyDataModel[Classification] | OntologyDataModel[Object]", answer_str: str
    ) -> list[ClassificationInstance] | ObjectInstance:
        """
        Validate a json response in accordance to the pydantic model.

        This function allows you to convert from a json object (e.g., coming from an llm)
        back to the encord "instance format".

        Args:
            answer_str: The json object as a raw string.

        Returns: a list of classification / object instances that you will then
            have to add to a label row.

        """
        answer = self.DataModel.model_validate_json(answer_str)
        # ^ if classification has a property per top-level classification in the ontology

        if self.DataModel.__name__ == OBJECTS_RADIO_MODEL:  # type: ignore
            ont_obj = answer.get_ontology_object()  # type: ignore
            ins = ont_obj.create_instance()

            if ont_obj.attributes:
                for attr_key, attr_val in vars(answer).items():
                    if attr_key == "feature_node_hash":
                        continue
                    attr_val.set_answer(ins)
            return ins
        else:
            answers = []
            for attr_val in vars(answer).values():
                ont_cls = self.ontology_lookup[attr_val.feature_node_hash]
                ins = ont_cls.create_instance()
                attr_val.set_answer(ins)
                answers.append(ins)

            return answers

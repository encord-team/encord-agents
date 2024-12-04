from encord.objects.attributes import ChecklistAttribute, RadioAttribute, TextAttribute
from encord.objects.common import Shape
from encord.objects.ontology_object import Object
from encord.objects.ontology_object_instance import ObjectInstance
from encord.objects.ontology_structure import OntologyStructure

from encord_agents.core.ontology import OntologyDataModel

uids = [
    "aaaaaaaa",
    "aaaabbbb",
    "bbbbaaaa",
    "aaaacccc",
    "ccccaaaa",
    "aaaadddd",
    "ddddaaaa",
    "aaaaeeee",
    "ffffaaaa",
    "aaaa0000",
    "1111aaaa",
    "aaaa2222",
    "3333aaaa",
    "4444aaaa",
    "33335555",
    "6666aaaa",
    "33337777",
    "8888aaaa",
    "33339999",
    "gggg0000",
    "ggggaaaa",
    "aaagggg2",
    "3ggggaaa",
    "ggggaaaa",
    "333gggg5",
    "6ggggaaa",
    "33gggg77",
    "888gggga",
    "3gggg999",
]


def test_simple_radio_attribute() -> None:
    # Create structure
    gen = iter(uids)
    struct = OntologyStructure()
    clf = struct.add_classification(feature_node_hash=next(gen))
    attr = clf.add_attribute(RadioAttribute, name="color", feature_node_hash=next(gen))
    for opt in ["red", "blue", "green"]:
        attr.add_option(label=opt, feature_node_hash=next(gen))

    model = OntologyDataModel(clf)
    answer = """{
      "color": {
        "feature_node_hash": "aaaabbbb",
        "choice": "blue"
      }
    }"""
    encord_classification_instances = model.validate_json(answer)

    assert len(encord_classification_instances) == 1
    assert encord_classification_instances[0].get_answer().value == "blue"  # type: ignore


def test_nested_radio_attribute() -> None:
    gen = iter(uids)
    # Create structure
    struct = OntologyStructure()
    clf = struct.add_classification(feature_node_hash=next(gen))
    attr = clf.add_attribute(RadioAttribute, name="color", feature_node_hash=next(gen))

    for opt in ["red", "blue", "green"]:
        ont_opt = attr.add_option(label=opt, feature_node_hash=next(gen))
        nattr = ont_opt.add_nested_attribute(RadioAttribute, "count", feature_node_hash=next(gen))
        nattr.add_option("0 to 5", feature_node_hash=next(gen))
        nattr.add_option("5 to 10", feature_node_hash=next(gen))
        nattr.add_option("10 to 15", feature_node_hash=next(gen))

    model = OntologyDataModel(clf)
    instances = model(
        """{ "color": { "feature_node_hash": "aaaabbbb", "choice": { "feature_node_hash": "bbbbaaaa", "count": { "feature_node_hash": "aaaacccc", "choice": "5 to 10" } } } }"""
    )
    assert len(instances) == 1
    assert instances[0].get_answer()


def test_simple_text_attribute() -> None:
    # Create structure
    gen = iter(uids)
    struct = OntologyStructure()
    clf = struct.add_classification(feature_node_hash=next(gen))
    clf.add_attribute(TextAttribute, name="color", feature_node_hash=next(gen))

    model = OntologyDataModel(clf)

    set_value = "my own free text"
    answer = f"""{{
      "color": {{
        "feature_node_hash": "{uids[1]}",
        "value": "{set_value}"
      }}
    }}"""
    encord_classification_instances = model.validate_json(answer)

    assert len(encord_classification_instances) == 1
    assert encord_classification_instances[0].get_answer() == set_value


def test_simple_checklist() -> None:
    # Create structure
    gen = iter(uids)
    struct = OntologyStructure()
    clf = struct.add_classification(feature_node_hash=next(gen))
    attr = clf.add_attribute(ChecklistAttribute, name="what can you see?", feature_node_hash=next(gen))
    for opt in ["blueberry", "strawberry", "leaves", "flies"]:
        attr.add_option(label=opt, feature_node_hash=next(gen))

    model = OntologyDataModel(clf)
    answer = """{
  "what_can_you_see": {
    "feature_node_hash": "aaaabbbb",
    "blueberry": true,
    "strawberry": false,
    "leaves": true,
    "flies": false
  }
}
"""
    encord_classification_instances = model.validate_json(answer)

    assert len(encord_classification_instances) == 1
    encord_answer = encord_classification_instances[0].get_answer()
    assert isinstance(encord_answer, list)
    assert len(encord_answer) == 2

    names = [a.title for a in encord_answer]
    assert "blueberry" in names
    assert "leaves" in names
    assert "strawberry" not in names
    assert "flies" not in names


def test_flat_objects() -> None:
    struct = OntologyStructure()
    ont_objects = [
        struct.add_object(obj_name, Shape.POLYGON) for obj_name in ["strawberry", "apple", "pineapple", "blueberry"]
    ]
    model = OntologyDataModel(ont_objects)
    answer = """{
    "choice": "blueberry"
}"""
    encord_answer = model.validate_json(answer)
    assert isinstance(encord_answer, ObjectInstance)
    assert encord_answer.object_name == "blueberry"


def test_nested_objects() -> None:
    gen = iter(uids)
    struct = OntologyStructure()

    def add_object(obj_name: str) -> Object:
        ont_obj = struct.add_object(obj_name, Shape.POLYGON, feature_node_hash=next(gen))
        attr = ont_obj.add_attribute(RadioAttribute, "count", feature_node_hash=next(gen))
        attr.add_option("0 to 5", feature_node_hash=next(gen))
        attr.add_option("6 to 10", feature_node_hash=next(gen))
        attr.add_option("10 to 15", feature_node_hash=next(gen))
        return ont_obj

    ont_objects = [add_object(obj_name) for obj_name in ["strawberry", "apple", "pineapple", "blueberry"]]
    model = OntologyDataModel(ont_objects)

    answer = """{
"choice": { "feature_node_hash": "6666aaaa", "count": { "feature_node_hash": "33337777", "choice": "6 to 10" } } }
"""
    encord_answer = model.validate_json(answer)
    assert isinstance(encord_answer, ObjectInstance)
    assert encord_answer.object_name == "blueberry"

    nested_answer = encord_answer.get_answer(encord_answer.ontology_item.attributes[0])
    assert nested_answer
    assert nested_answer.label == "6 to 10"  # type: ignore


def test_only_some_nested_radio_attributes() -> None:
    gen = iter(uids)
    # Create structure
    struct = OntologyStructure()
    clf = struct.add_classification(feature_node_hash=next(gen))
    attr = clf.add_attribute(RadioAttribute, name="color", feature_node_hash=next(gen))

    for opt in ["red", "blue", "green"]:
        ont_opt = attr.add_option(label=opt, feature_node_hash=next(gen))
        if ont_opt.label == "red":
            continue
        nattr = ont_opt.add_nested_attribute(RadioAttribute, "count", feature_node_hash=next(gen))
        nattr.add_option("0 to 5", feature_node_hash=next(gen))
        nattr.add_option("5 to 10", feature_node_hash=next(gen))
        nattr.add_option("10 to 15", feature_node_hash=next(gen))

    model = OntologyDataModel(clf)
    instances = model(
        """{ "color": { "feature_node_hash": "aaaabbbb", "choice": { "feature_node_hash": "bbbbaaaa", "count": { "feature_node_hash": "aaaacccc" } } } }"""
    )
    assert len(instances) == 1
    assert instances[0].get_answer()
    assert instances[0].get_answer().label == "red"  # type: ignore
    # ---
    instances = model(
        """{ "color": { "feature_node_hash": "aaaabbbb", "choice": { "feature_node_hash": "aaaacccc", "count": { "feature_node_hash": "ccccaaaa", "choice": "5 to 10" } } } }"""
    )
    assert len(instances) == 1
    assert instances[0].get_answer()

    ins = instances[0]
    nested_option = ins.get_answer(attribute=ins.ontology_item.attributes[0].options[1].nested_options[0])
    assert nested_option.label == "5 to 10"  # type: ignore


def test_only_some_nested_objects() -> None:
    gen = iter(uids)
    struct = OntologyStructure()

    def add_object(obj_name: str) -> Object:
        ont_obj = struct.add_object(obj_name, Shape.POLYGON, feature_node_hash=next(gen))
        if obj_name == "blueberry":
            return ont_obj

        attr = ont_obj.add_attribute(RadioAttribute, "count", feature_node_hash=next(gen))
        attr.add_option("0 to 5", feature_node_hash=next(gen))
        attr.add_option("6 to 10", feature_node_hash=next(gen))
        attr.add_option("10 to 15", feature_node_hash=next(gen))
        return ont_obj

    ont_objects = [add_object(obj_name) for obj_name in ["strawberry", "apple", "pineapple", "blueberry"]]
    model = OntologyDataModel(ont_objects)
    answer = """{
"choice": { "feature_node_hash": "6666aaaa", "count": { "feature_node_hash": "33337777", "choice": "6 to 10" } } }
"""

    encord_answer = model.validate_json(answer)
    assert isinstance(encord_answer, ObjectInstance)
    assert encord_answer.object_name == "blueberry"
    assert len(encord_answer.ontology_item.attributes) == 0

    answer = f"""{{
"choice": {{ "feature_node_hash": "{uids[0]}", "count": {{ "feature_node_hash": "{uids[1]}", "choice": "6 to 10" }} }} }}
"""
    encord_answer = model.validate_json(answer)
    nested_answer = encord_answer.get_answer(encord_answer.ontology_item.attributes[0])
    assert nested_answer
    assert nested_answer.label == "6 to 10"  # type: ignore


def test_just_one_nested_object() -> None:
    gen = iter(uids)
    struct = OntologyStructure()

    def add_object(obj_name: str) -> Object:
        ont_obj = struct.add_object(obj_name, Shape.POLYGON, feature_node_hash=next(gen))
        if obj_name == "blueberry":
            return ont_obj

        attr = ont_obj.add_attribute(RadioAttribute, "count", feature_node_hash=next(gen))
        attr.add_option("0 to 5", feature_node_hash=next(gen))
        attr.add_option("6 to 10", feature_node_hash=next(gen))
        attr.add_option("10 to 15", feature_node_hash=next(gen))
        return ont_obj

    ont_obj = add_object("my_single_object")
    model = OntologyDataModel(ont_obj)

    answer = """{
  "choice": {
    "feature_node_hash": "aaaaaaaa",
    "count": {
      "feature_node_hash": "aaaabbbb",
      "choice": "10 to 15"
    }
  }
}
"""

    encord_answer = model.validate_json(answer)
    assert isinstance(encord_answer, ObjectInstance)
    assert encord_answer.object_name == "my_single_object"
    assert len(encord_answer.ontology_item.attributes) == 1
    attr = encord_answer.ontology_item.attributes[0]
    nested_answer = encord_answer.get_answer(attr)
    assert nested_answer.label == "10 to 15"  # type: ignore

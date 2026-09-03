"""A custom agent that routes its task through the workflow by returning a `decision`.

Register this endpoint on an agent stage whose pathways are named `accept` and `reject`.
When the workflow triggers the agent, Encord matches the returned `decision` against
those pathway names and moves the task along that pathway.

Note that `decision` is only honoured for workflow-triggered runs. The same endpoint
invoked from the Label Editor has no task to route, so Encord ignores `decision` there
and only `message` is surfaced -- which means one endpoint can serve both, as below.
"""

from encord.objects import Shape
from encord.objects.coordinates import BoundingBoxCoordinates
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.ontology_object_instance import ObjectInstance
from fastapi import Depends
from typing_extensions import Annotated

from encord_agents.core.data_model import EditorAgentResponse
from encord_agents.fastapi.cors import get_encord_app
from encord_agents.fastapi.dependencies import FrameData, dep_label_row

app = get_encord_app()

# Reject a frame whose boxes are implausibly small; a real agent would do something
# more interesting here. Coordinates are normalised, so this is a fraction of the image.
MIN_BOX_AREA = 0.001


def _relative_box_area(box: ObjectInstance, frame: int) -> float:
    coords = box.get_annotation(frame).coordinates
    # Guaranteed by the shape filter below, and asserted rather than duck-typed so a
    # non-box slipping through fails here instead of quietly scoring as full-size.
    assert isinstance(coords, BoundingBoxCoordinates)
    return coords.width * coords.height


@app.post("/qa_routing")
def qa_routing(
    frame_data: FrameData,
    lr: Annotated[LabelRowV2, Depends(dep_label_row)],
) -> EditorAgentResponse:
    # Narrow to the shape this agent understands before touching any coordinates.
    # Ontologies mix shapes, and only bounding boxes have a width and a height.
    boxes = [
        instance
        for instance in lr.get_object_instances(filter_frames=frame_data.frame)
        if instance.ontology_item.shape == Shape.BOUNDING_BOX
    ]
    too_small = [box for box in boxes if _relative_box_area(box, frame_data.frame) < MIN_BOX_AREA]

    if too_small:
        # The pathway name must match the stage's configuration exactly; an unmatched
        # name fails the execution rather than falling back to the default pathway.
        return EditorAgentResponse(
            decision="reject",
            message=f"{len(too_small)} of {len(boxes)} box(es) are too small.",
        )

    return EditorAgentResponse(decision="accept", message=f"Checked {len(boxes)} box(es).")

"""
Pre-label video with bounding boxes from example model.

This example demonstrates how to use the
`encord_agents.tasks.dependencies.dep_video_iterator`
to iterate over all the frames.
Example predictions are added to the label row and saved.
"""

import random
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from encord.objects.coordinates import BoundingBoxCoordinates
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.project import Project
from numpy.typing import NDArray
from typing_extensions import Annotated

from encord_agents.core.data_model import Frame
from encord_agents.tasks import Depends, Runner
from encord_agents.tasks.dependencies import dep_video_iterator

runner = Runner(project_hash="a918b378-1041-489b-b228-ab684c3fb026")


# === BEGIN FAKE MODEL === #
@dataclass
class ModelPrediction:
    label: int
    coords: BoundingBoxCoordinates
    conf: float


def fake_predict(image: NDArray[np.uint8]) -> list[ModelPrediction]:
    return [
        ModelPrediction(
            label=random.choice(range(10)),
            coords=BoundingBoxCoordinates(
                top_left_x=random.random() * 0.5,
                top_left_y=random.random() * 0.5,
                width=random.random() * 0.5,
                height=random.random() * 0.5,
            ),
            conf=random.random() + 0.5,
        )
        for _ in range(10)
    ]


model = fake_predict
# === END FAKE MODEL === #


@runner.stage(stage="pre-label")
def run_something(
    lr: LabelRowV2, project: Project, frames: Annotated[Iterable[Frame], Depends(dep_video_iterator)]
) -> str:
    ontology = project.ontology_structure

    for frame in frames:
        outputs = model(frame.content)
        for output in outputs:
            ins = ontology.objects[output.label].create_instance()
            ins.set_for_frames(frames=frame.frame, coordinates=output.coords, confidence=output.conf)

            lr.add_object_instance(ins)

    lr.save()
    return "annotate"  # Tell where the task should go


if __name__ == "__main__":
    runner.run()

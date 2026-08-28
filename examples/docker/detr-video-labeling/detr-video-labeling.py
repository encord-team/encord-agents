import argparse
from pathlib import Path
from typing import Annotated, Callable, Generator, Iterator

import cv2
import numpy as np
import torch
from encord.objects.common import Shape
from encord.objects.coordinates import BoundingBoxCoordinates
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.ontology_object import Object
from encord.project import Project
from transformers import RTDetrForObjectDetection, RTDetrImageProcessor

from encord_agents.core.data_model import Frame
from encord_agents.core.utils import batch_iterator
from encord_agents.tasks import Depends, Runner
from encord_agents.tasks.dependencies import dep_asset


class OntologyVerifiedRunner(Runner):
    def __init__(  # type: ignore[no-untyped-def]
        self,
        rt_detr_name: str = "PekingU/rtdetr_r50vd",
        device: str | torch.device | None = None,
        *args,
        **kwargs,
    ):
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = RTDetrForObjectDetection.from_pretrained(rt_detr_name).to(self.device)
        self.image_processor = RTDetrImageProcessor.from_pretrained(rt_detr_name)
        self.label_names: dict[int, Object] = {}

        super().__init__(*args, **kwargs)

    def dep_model_and_processor(self) -> tuple[RTDetrForObjectDetection, RTDetrImageProcessor]:
        return self.model, self.image_processor

    def _validate_project(self, project: Project | None) -> None:  # type: ignore[override]
        super()._validate_project(project)
        if project is None:
            return

        # === Additional stuff ===
        label_names = set(self.model.config.label2id.keys())
        self.id2ontobj: dict[int, Object] = {}
        assert self.project
        for obj in self.project.ontology_structure.objects:
            if obj.name in label_names and obj.shape == Shape.BOUNDING_BOX:
                self.id2ontobj[self.model.config.label2id[obj.name]] = obj

        assert self.id2ontobj, "No bounding box objects found of the following names: " f"`{label_names}`"


def torch_box_to_coords(box: torch.Tensor, frame: Frame) -> BoundingBoxCoordinates:
    h, w = frame.content.shape[:2]
    x1, y1, x2, y2 = box.cpu().tolist()
    bw, bh = x2 - x1, y2 - y1
    return BoundingBoxCoordinates(
        top_left_x=x1 / w,
        top_left_y=y1 / h,
        width=bw / w,
        height=bh / h,
    )


def iter_video_with_sampling_rate(
    sampling_rate: float = 1 / 25,
) -> Callable[[Path], Generator[Iterator[Frame], None, None]]:
    """
    Args:
        sampling_rate: The proportion of frames to sample. 1/25 samples 1 frame per 25 frames.
    """

    def _iter(video_path: Path) -> Generator[Frame, None, None]:
        """
        Args:
            video_path: The file path to the video you wish to iterate.

        Raises:
            Exception: If the video file could not be opened properly.

        Yields:
            Frames from the video.
        """
        cap = cv2.VideoCapture(video_path.as_posix())
        if not cap.isOpened():
            raise Exception("Error opening video file.")

        frame_num = 0
        while True:
            # Set the frame position before reading
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            if not ret:
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            yield Frame(frame=frame_num, content=rgb_frame.astype(np.uint8))

            # Skip frames according to sampling rate
            frame_num += int(1 / sampling_rate)

        cap.release()

    def yield_from(video_path: Annotated[Path, Depends(dep_asset)]) -> Generator[Iterator[Frame], None, None]:
        yield _iter(video_path)

    return yield_from


def predict_batch(
    model: RTDetrForObjectDetection, processor: RTDetrImageProcessor, frames: list[Frame], label_row: LabelRowV2
) -> None:
    images = [frame.content for frame in frames]
    inputs = processor(images=images, return_tensors="pt")

    with torch.inference_mode():
        outputs = model(**inputs.to(model.device))

    target_sizes = torch.tensor([frame.content.shape[:2] for frame in frames])
    results = processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold=0.3)

    for result, frame in zip(results, frames):
        for label, box, score in zip(result["labels"], result["boxes"], result["scores"]):
            label = label.item()
            if label not in runner.id2ontobj:
                continue

            obj = runner.id2ontobj[label]
            ins = obj.create_instance()
            ins.set_for_frames(
                frames=frame.frame,
                coordinates=torch_box_to_coords(box, frame),
                manual_annotation=False,
                confidence=score.item(),
            )
            label_row.add_object_instance(ins)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process the project hash.")
    # Add the project-hash argument
    parser.add_argument("--project-hash", type=str, required=True, help="Hash value of the project")

    # Parse the arguments
    args = parser.parse_args()
    project_hash = args.project_hash
    runner = OntologyVerifiedRunner(project_hash=project_hash)
    runner.was_called_from_cli = True
    assert runner.valid_stages, "No agent stage found"
    workflow_stage = runner.valid_stages[0]
    assert workflow_stage.pathways, "Require at least one pathway (This should be impossible)"

    @runner.stage(stage=workflow_stage.title, overwrite=True)
    def pre_label(
        model_specs: Annotated[
            tuple[RTDetrForObjectDetection, RTDetrImageProcessor], Depends(runner.dep_model_and_processor)
        ],
        lr: LabelRowV2,
        frame_iter: Annotated[Iterator[Frame], Depends(iter_video_with_sampling_rate(sampling_rate=1 / 60))],
    ) -> str:
        batch_size = 64
        model, processor = model_specs
        for frame_batch in batch_iterator(iter(frame_iter), batch_size=batch_size):
            predict_batch(model, processor, frame_batch, lr)

        if lr.get_object_instances():
            lr.save()
            # 'Irrelevant'
            return workflow_stage.pathways[0].name
        else:
            # 'Relevant'
            return workflow_stage.pathways[1].name

    runner()

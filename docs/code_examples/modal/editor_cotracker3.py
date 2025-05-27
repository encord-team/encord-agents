from pathlib import Path

import modal
from encord.objects.coordinates import (
    PointCoordinate,
)
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.ontology_object_instance import ObjectInstance
from fastapi import Depends
from typing_extensions import Annotated

from encord_agents.fastapi.dependencies import (
    FrameData,
    dep_asset,
    dep_label_row,
    dep_objects,
)

# 1. Define the Modal Image
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libgl1", "libglib2.0-0", "wget")
    .run_commands(
        "wget https://huggingface.co/facebook/cotracker3/resolve/main/scaled_offline.pth",
    )
    .pip_install(
        "fastapi[standard]",
        "encord-agents",
        "torch",
        "torchvision",
        "tqdm",
        "imageio[ffmpeg]",
    )
    .add_local_python_source("cotracker")
)

# 2. Define the Modal app

app = modal.App(name="encord-agents-cotracker-3-with-model", image=image)


# Pull in dependency from cotracker to reduce required dependencies
def read_video_from_path(path):
    import imageio
    import numpy as np

    try:
        reader = imageio.get_reader(path)
    except Exception as e:
        print("Error opening video file: ", e)
        return None
    frames = []
    for i, im in enumerate(reader):
        frames.append(np.array(im))
    return np.stack(frames)


# 3. Define the endpoint with access to the secret that we set up.
@app.function(secrets=[modal.Secret.from_name("encord-ssh-key")], gpu="L4")
@modal.web_endpoint(method="POST")
def cotracker3(
    frame_data: FrameData,
    lr: Annotated[LabelRowV2, Depends(dep_label_row)],
    object_instances: Annotated[list[ObjectInstance], Depends(dep_objects)],
    asset: Annotated[Path, Depends(dep_asset)],
):
    import imageio
    import numpy
    import torch
    from cotracker.predictor import CoTrackerPredictor

    model = CoTrackerPredictor(checkpoint="/scaled_offline.pth")
    if torch.cuda.is_available():
        model = model.cuda()

    assert len(object_instances) == 1
    obj_inst = object_instances[0]
    video = read_video_from_path(asset)
    video_tensor = torch.from_numpy(video).permute(0, 3, 1, 2)[None].float()

    if torch.cuda.is_available():
        video_tensor = video_tensor.cuda()
    annotation = obj_inst.get_annotation(frame_data.frame)
    assert isinstance(annotation.coordinates, PointCoordinate)
    assert lr.width
    assert lr.height
    query = torch.tensor(
        [
            # Frame num, W,H
            [
                frame_data.frame,
                annotation.coordinates.x * lr.width,
                annotation.coordinates.y * lr.height,
            ],
        ]
    )
    if torch.cuda.is_available():
        query = query.cuda()
    pred_tracks, _ = model(video_tensor, queries=query[None])
    for frame_num, coord in enumerate(pred_tracks.reshape(-1, 2)):
        try:
            obj_inst.set_for_frames(
                coordinates=PointCoordinate(x=float(coord[0]) / lr.width, y=float(coord[1]) / lr.height),
                frames=frame_num,
            )
        except Exception:
            continue
    lr.save()

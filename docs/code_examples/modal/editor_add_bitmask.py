"""
Steps to make it work:


# 1. Install modal and encord-agents:
```
python -m pip install modal "encord-agents[vision]" "fastapi[standard]"
```

# 2. Log in to modal
```
modal setup
```

# 3. Configure secret [see here](https://agents-docs.encord.com/editor_agents/modal/#setting-up-authentication).

# 4. Execute with modal
```
modal serve editor_add_bitmask.py
```

# (5.) To test it, run
```
encord-agents test custom '<url_that_modal_printed>' '<editor_url>'
```

See more [here](https://agents-docs.encord.com/editor_agents/modal/).
"""

import cv2
import modal
import numpy as np
from encord.objects.bitmask import BitmaskCoordinates
from encord.objects.common import Shape
from fastapi import Depends
from typing_extensions import Annotated

from encord_agents import FrameData
from encord_agents.fastapi.dependencies import LabelRowV2, dep_label_row

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "libgl1",
        "libglib2.0-0",
    )
    .pip_install(
        "fastapi[standard]",
        "encord-agents[vision]",
    )
)
app = modal.App(name="encord-agents-add-ball", image=image)


@app.function(secrets=[modal.Secret.from_name("encord-ssh-key")])
@modal.web_endpoint(method="POST", docs=True)
def put_ball_on_image(
    frame_data: FrameData,
    label_row: Annotated[LabelRowV2, Depends(dep_label_row)],
):
    # Find a bitmask ontology object
    bitmask_object = next(
        (o for o in label_row.ontology_structure.objects if o.shape == Shape.BITMASK),
        None,
    )
    bitmask_object = next(
        (o for o in label_row.ontology_structure.objects if o.shape == Shape.BITMASK),
        None,
    )
    if not bitmask_object:
        return

    # Ensure we can read image width/height
    w, h = label_row.width, label_row.height
    if w is None or h is None:
        return

    # Construct bitmask with ball in the center
    cw, ch = w // 2, h // 2
    radius = min(cw, ch) // 2
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, (cw, ch), radius, 255, -1)  # type: ignore

    # Add it as a label
    ins = bitmask_object.create_instance()
    ins.set_for_frames(
        frames=frame_data.frame,
        confidence=0.8,
        coordinates=BitmaskCoordinates(mask > 0),
    )
    label_row.add_object_instance(ins)

    # Save update
    label_row.save()

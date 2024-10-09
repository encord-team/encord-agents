"""
You can try this editor agent by running 

```shell
encord-agents gcp init <project_name> --src-file /path/to/this/file/add_bounding_box.py
cd <project_name>
ENCORD_SSH_KEY_FILE=/path/to/private_key encord-agents gcp run add_bounding_box
```

Please see README for more details.
"""

from encord.objects.coordinates import BoundingBoxCoordinates
from encord.objects.ontology_labels_impl import LabelRowV2

from encord_agents.core.data_model import FrameData
from encord_agents.gcp import editor_agent


@editor_agent()
def add_bounding_box(frame_data: FrameData, label_row: LabelRowV2) -> None:
    ins = label_row.ontology_structure.objects[0].create_instance()
    ins.set_for_frames(
        frames=frame_data.frame,
        coordinates=BoundingBoxCoordinates(
            top_left_x=0.2, top_left_y=0.2, width=0.6, height=0.6
        ),
    )
    label_row.add_object_instance(ins)
    label_row.save()

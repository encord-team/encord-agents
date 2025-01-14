from dataclasses import dataclass
from typing import Literal, overload
from uuid import UUID

import numpy as np
from encord.objects.ontology_object_instance import ObjectInstance
from numpy.typing import NDArray
from pydantic import BaseModel, Field

from encord_agents.core.vision import DATA_TYPES, b64_encode_image

Base64Formats = Literal[".jpeg", ".jpg", ".png"]


class LabelRowMetadataIncludeArgs(BaseModel):
    """
    Warning, including metadata via label rows is good for _reading_ metadata
    **not** for writing to the metadata.

    If you need to write to metadata, use the `dep_storage_item` dependencies instead.
    """

    include_workflow_graph_node: bool = True
    include_client_metadata: bool = False
    include_images_data: bool = False
    include_all_label_branches: bool = False


class LabelRowInitialiseLabelsArgs(BaseModel):
    """
    Arguments used to specify how to initialise labels via the SDK.

    The arguments are passed to `LabelRowV2.initialise_labels`.
    """

    include_object_feature_hashes: set[str] | None = None
    include_classification_feature_hashes: set[str] | None = None
    include_reviews: bool = False
    overwrite: bool = False
    include_signed_url: bool = False


class FrameData(BaseModel):
    """
    Holds the data sent from the Encord Label Editor at the time of triggering the agent.
    """

    project_hash: UUID = Field(alias="projectHash")
    """
    The identifier of the given project.
    """
    data_hash: UUID = Field(alias="dataHash")
    """
    The identifier of the given data asset.
    """
    frame: int = Field(ge=0)
    """
    The frame number. If single image, it's default 0.
    """


@dataclass(frozen=True)
class Frame:
    """
    A dataclass to hold the content of one frame in a video.
    """

    frame: int
    """
    The frame number within the video
    """
    content: "NDArray[np.uint8]"
    """
    An [h,w,c] np.array with color channels RGB.
    """

    @overload
    def b64_encoding(
        self,
        image_format: Base64Formats = ".jpeg",
        output_format: Literal["raw", "url"] = "raw",
    ) -> str: ...

    @overload
    def b64_encoding(
        self,
        image_format: Literal[".jpeg", ".jpg", ".png"] = ".jpeg",
        output_format: Literal["openai", "anthropic"] = "openai",
    ) -> dict[str, str | dict[str, str]]: ...

    def b64_encoding(
        self,
        image_format: Literal[".jpeg", ".jpg", ".png"] = ".jpeg",
        output_format: Literal["url", "openai", "anthropic", "raw"] = "url",
    ) -> str | dict[str, str | dict[str, str]]:
        """
        Get a base64 representation of the image content.

        This method allows you to convert the content into a base64 representation
        based on various different image encodings.
        This is useful, e.g., for prompting LLMs with image content.


        Please see details for formats below.

        Args:
            image_format: Which type of image encoding to use.
            output_format: Different common formats.
                - `raw`: the image content as a raw b64 string
                - `url`: url encoded image content. Compatible with, e.g., `<img src="<the_encoding>" />`
                - `openai`: a dict with `type` and `image_url` keys
                _ `anthropic`: a dict with `media_type`, `type`, and `data` keys.

        Returns: a dict or string depending on `output_format`.

        """
        b64_str = b64_encode_image(self.content, image_format)
        if output_format == "raw":
            return b64_str

        media_type = DATA_TYPES.get(image_format, f"image/{image_format.replace('.', '')}")
        image_url = f"data:{media_type};base64,{b64_str}"
        if output_format == "url":
            return image_url
        elif output_format == "openai":
            return {
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                },
            }
        elif output_format == "anthropic":
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64_str,
                },
            }


@dataclass(frozen=True)
class InstanceCrop(Frame):
    """
    A dataclass to hold the frame content of one object instance in a video or image.
    """

    instance: ObjectInstance
    r"""
    The [ObjectInstance](https://docs.encord.com/sdk-documentation/sdk-references/ObjectInstance#objectinstance){ target="\_blank", rel="noopener noreferrer" } associated to the crop.
    """

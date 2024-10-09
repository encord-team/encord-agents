import logging
from functools import wraps
from pathlib import Path
from typing import Callable, Literal, Protocol, cast, overload

from encord.objects.ontology_labels_impl import LabelRowV2
from flask import Request, Response, make_response

from encord_agents import FrameData
from encord_agents.core.utils import download_asset, get_initialised_label_row


class RequestLabelRowAndAssetCallable(Protocol):
    def __call__(
        self,
        frame_data: FrameData,
        label_row: LabelRowV2,
        asset: Path,
    ) -> None: ...


class RequestAndLabelRowCallable(Protocol):
    def __call__(
        self,
        frame_data: FrameData,
        label_row: LabelRowV2,
    ) -> None: ...


AgentFunction = RequestAndLabelRowCallable | RequestLabelRowAndAssetCallable

AgentWrapperWithAsset = Callable[
    [RequestLabelRowAndAssetCallable],
    Callable[[Request], Response],
]
AgentWrapperNoAsset = Callable[
    [RequestAndLabelRowCallable],
    Callable[[Request], Response],
]
AgentWrapper = AgentWrapperNoAsset | AgentWrapperWithAsset


def generate_response() -> Response:
    """
    Generate a Response object with status 200 in order to tell the FE that the function has finished successfully.
    :return: Response object with the right CORS settings.
    """
    response = make_response("")
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@overload
def editor_agent(
    asset: Literal[True],
) -> AgentWrapperWithAsset: ...


@overload
def editor_agent(
    asset: Literal[False] = False,
) -> AgentWrapperNoAsset: ...


def editor_agent(
    asset: bool = False,
) -> AgentWrapper:
    def context_wrapper_inner(func: AgentFunction) -> Callable:
        @wraps(func)  # type: ignore
        def wrapper(request: Request) -> Response:
            frame_data = FrameData.model_validate_json(request.data)
            logging.info(f"Request: {frame_data}")

            label_row = get_initialised_label_row(frame_data)
            if not asset:
                fn = cast(RequestAndLabelRowCallable, func)
                fn(frame_data, label_row=label_row)
            else:
                fn = cast(RequestLabelRowAndAssetCallable, func)
                with download_asset(label_row, frame_data.frame) as asset_path:
                    fn(
                        frame_data,
                        label_row=label_row,
                        asset=asset_path,
                    )

            return generate_response()

        return wrapper

    return context_wrapper_inner

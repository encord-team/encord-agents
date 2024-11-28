import logging
from contextlib import ExitStack
from functools import wraps
from typing import Any, Callable

import orjson
from encord.objects.ontology_labels_impl import LabelRowV2
from flask import Request, Response, make_response

from encord_agents import FrameData
from encord_agents.core.dependencies.models import Context
from encord_agents.core.dependencies.utils import get_dependant, solve_dependencies
from encord_agents.core.utils import get_user_client

AgentFunction = Callable[..., Any]


def generate_response() -> Response:
    """
    Generate a Response object with status 200 in order to tell the FE that the function has finished successfully.
    :return: Response object with the right CORS settings.
    """
    response = make_response("")
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


from pydantic import BaseModel

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


def editor_agent(*, label_row_metadata_include_args: LabelRowMetadataIncludeArgs | None = None) -> Callable[[AgentFunction], Callable[[Request], Response]]:
    """
    Wrapper to make resources available for gcp editor agents.

    The editor agents are intended to be used via dependency injections.
    You can learn more via out [documentation](https://agents-docs.encord.com).
    """

    def context_wrapper_inner(func: AgentFunction) -> Callable:
        dependant = get_dependant(func=func)

        @wraps(func)
        def wrapper(request: Request) -> Response:
            frame_data = FrameData.model_validate_json(orjson.dumps(request.form.to_dict()))
            logging.info(f"Request: {frame_data}")

            client = get_user_client()
            project = client.get_project(str(frame_data.project_hash))

            label_row: LabelRowV2 | None = None
            if dependant.needs_label_row:
                include_args = {}
                if label_row_metadata_include_args is not None:
                    include_args = label_row_metadata_include_args.model_dump()
                label_row = project.list_label_rows_v2(data_hashes=[str(frame_data.data_hash)], **include_args)[0]
                label_row.initialise_labels(include_signed_url=True)

            context = Context(project=project, label_row=label_row, frame_data=frame_data)
            with ExitStack() as stack:
                dependencies = solve_dependencies(context=context, dependant=dependant, stack=stack)
                func(**dependencies.values)
            return generate_response()

        return wrapper

    return context_wrapper_inner

import logging
import re
from contextlib import ExitStack
from functools import wraps
from http import HTTPStatus
from typing import Any, Callable

from encord.exceptions import AuthorisationError
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.storage import StorageItem
from fastapi import HTTPException
from flask import Request, Response, make_response

from encord_agents import FrameData
from encord_agents.core.constants import EDITOR_TEST_REQUEST_HEADER, ENCORD_DOMAIN_REGEX
from encord_agents.core.data_model import LabelRowInitialiseLabelsArgs, LabelRowMetadataIncludeArgs
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


def editor_agent(
    *,
    label_row_metadata_include_args: LabelRowMetadataIncludeArgs | None = None,
    label_row_initialise_labels_args: LabelRowInitialiseLabelsArgs | None = None,
) -> Callable[[AgentFunction], Callable[[Request], Response]]:
    """
    Wrapper to make resources available for gcp editor agents.

    The editor agents are intended to be used via dependency injections.
    You can learn more via out [documentation](https://agents-docs.encord.com).

    Args:
        label_row_metadata_include_args: arguments to overwrite default arguments
            on `project.list_label_rows_v2()`.
        label_row_initialise_labels_args: Arguments to overwrite default arguments
            on `label_row.initialise_labels(...)`

    Returns:
        A wrapped function suitable for gcp functions.
    """

    def context_wrapper_inner(func: AgentFunction) -> Callable[[Request], Response]:
        dependant = get_dependant(func=func)
        cors_regex = re.compile(ENCORD_DOMAIN_REGEX)

        @wraps(func)
        def wrapper(request: Request) -> Response:
            if request.method == "OPTIONS":
                response = make_response("")
                response.headers["Vary"] = "Origin"

                if not cors_regex.fullmatch(request.origin):
                    response.status_code = 403
                    return response

                headers = {
                    "Access-Control-Allow-Origin": request.origin,
                    "Access-Control-Allow-Methods": "POST",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Max-Age": "3600",
                }
                response.headers.update(headers)
                response.status_code = 204
                return response

            if request.headers.get(EDITOR_TEST_REQUEST_HEADER):
                return generate_response()
            if not request.is_json:
                raise Exception("Request should be JSON. Migrated over to new format")
            frame_data = FrameData.model_validate(request.get_json())
            logging.info(f"Request: {frame_data}")

            client = get_user_client()
            try:
                project = client.get_project(frame_data.project_hash)
            except AuthorisationError:
                response = make_response()
                response.status_code = HTTPStatus.FORBIDDEN
                return response

            label_row: LabelRowV2 | None = None
            if dependant.needs_label_row:
                include_args = label_row_metadata_include_args or LabelRowMetadataIncludeArgs()
                init_args = label_row_initialise_labels_args or LabelRowInitialiseLabelsArgs()
                label_row = project.list_label_rows_v2(
                    data_hashes=[str(frame_data.data_hash)], **include_args.model_dump()
                )[0]
                label_row.initialise_labels(**init_args.model_dump())

            storage_item: StorageItem | None = None
            if dependant.needs_storage_item:
                if label_row is None:
                    label_row = project.list_label_rows_v2(data_hashes=[frame_data.data_hash])[0]
                assert label_row.backing_item_uuid, "This is a server response so guaranteed to have this"
                storage_item = client.get_storage_item(label_row.backing_item_uuid)

            context = Context(project=project, label_row=label_row, frame_data=frame_data, storage_item=storage_item)
            with ExitStack() as stack:
                dependencies = solve_dependencies(context=context, dependant=dependant, stack=stack)
                func(**dependencies.values)
            return generate_response()

        return wrapper

    return context_wrapper_inner

import logging
import re
from contextlib import ExitStack
from functools import wraps
from http import HTTPStatus
from typing import Any, Callable

from encord.exceptions import AuthorisationError
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.storage import StorageItem
from flask import Request, Response, make_response
from pydantic_core import to_jsonable_python

from encord_agents import FrameData
from encord_agents.core.constants import EDITOR_TEST_REQUEST_HEADER, ENCORD_DOMAIN_REGEX
from encord_agents.core.data_model import (
    EditorAgentResponse,
    LabelRowInitialiseLabelsArgs,
    LabelRowMetadataIncludeArgs,
)
from encord_agents.core.dependencies.models import Context
from encord_agents.core.dependencies.utils import get_dependant, solve_dependencies
from encord_agents.core.exceptions import EncordEditorAgentException
from encord_agents.core.utils import get_user_client

AgentFunction = Callable[..., Any]


def _generate_response(body: str = "", status_code: HTTPStatus | None = None) -> Response:
    """
    Generate a Response object with status 200 in order to tell the FE that the function has finished successfully.
    :return: Response object with the right CORS settings.
    """
    response = make_response(body)
    if status_code:
        response.status_code = status_code
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


def editor_agent(
    *,
    label_row_metadata_include_args: LabelRowMetadataIncludeArgs | None = None,
    label_row_initialise_labels_args: LabelRowInitialiseLabelsArgs | None = None,
    custom_cors_regex: str | None = None,
) -> Callable[[AgentFunction], Callable[[Request], Response]]:
    """
    Wrapper to make resources available for gcp editor agents.

    The editor agents are intended to be used using dependency injections.
    You can learn more via out [documentation](https://agents-docs.encord.com).

    Args:
        label_row_metadata_include_args: arguments to overwrite default arguments
            on `project.list_label_rows_v2()`.
        label_row_initialise_labels_args: Arguments to overwrite default arguments
            on `label_row.initialise_labels(...)`
        custom_cors_regex: A regex to use for the CORS settings. If not provided, the default regex is used.
            Only required if the agent is not deployed on Encord's platform.

    Returns:
        A wrapped function suitable for gcp functions.
    """

    def context_wrapper_inner(func: AgentFunction) -> Callable[[Request], Response]:
        dependant = get_dependant(func=func)
        cors_regex = re.compile(custom_cors_regex or ENCORD_DOMAIN_REGEX)

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
                    "Access-Control-Allow-Headers": f"Content-Type, {EDITOR_TEST_REQUEST_HEADER}",
                    "Access-Control-Max-Age": "3600",
                }
                response.headers.update(headers)
                response.status_code = 204
                return response

            if request.headers.get(EDITOR_TEST_REQUEST_HEADER):
                logging.info("Editor test request")
                return _generate_response()
            if not request.is_json:
                raise Exception("Request should be JSON. Migrated over to new format")
            frame_data = FrameData.model_validate(request.get_json())
            logging.info(f"Request: {frame_data}")

            client = get_user_client()
            try:
                project = client.get_project(frame_data.project_hash)
            except AuthorisationError as err:
                response = _generate_response(to_jsonable_python({"message": err.message}), HTTPStatus.FORBIDDEN)
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
                    # include_children to handle children of data groups
                    label_row = project.list_label_rows_v2(data_hashes=[frame_data.data_hash], include_children=True)[0]
                assert label_row.backing_item_uuid, "This is a server response so guaranteed to have this"
                try:
                    storage_item = client.get_storage_item(label_row.backing_item_uuid)
                except AuthorisationError as err:
                    response = _generate_response(to_jsonable_python({"message": err.message}), HTTPStatus.FORBIDDEN)
                    return response

            context = Context(project=project, label_row=label_row, frame_data=frame_data, storage_item=storage_item)
            result: Any | None | EditorAgentResponse = None
            with ExitStack() as stack:
                try:
                    # Solving dependencies can execute arbitrary code including fetch from Encord platform
                    # e.g: Get storage item which can throw error
                    dependencies = solve_dependencies(context=context, dependant=dependant, stack=stack)
                except AuthorisationError as err:
                    response = _generate_response(to_jsonable_python({"message": err.message}), HTTPStatus.FORBIDDEN)
                    return response
                try:
                    result = func(**dependencies.values)
                    if isinstance(result, EditorAgentResponse):
                        response = _generate_response(result.model_dump_json(), HTTPStatus.OK)
                        return response
                except EncordEditorAgentException as exc:
                    response = _generate_response(to_jsonable_python(exc.json_response_body), HTTPStatus.BAD_REQUEST)
                    return response
            return _generate_response()

        return wrapper

    return context_wrapper_inner

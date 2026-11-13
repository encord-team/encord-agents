import logging
import re
from contextlib import ExitStack
from functools import wraps
from http import HTTPStatus
from typing import Any, Callable, Sequence

from encord.exceptions import AuthorisationError
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.storage import StorageItem
from flask import Request, Response, make_response
from pydantic import ValidationError
from pydantic_core import to_jsonable_python

from encord_agents import FrameData
from encord_agents.core.constants import (
    AGENT_RUN_TOKEN_HEADER,
    EDITOR_TEST_REQUEST_HEADER,
    ENCORD_DOMAIN_REGEX,
    HEADER_CLOUD_TRACE_CONTEXT,
)
from encord_agents.core.data_model import (
    EditorAgentResponse,
    LabelRowInitialiseLabelsArgs,
    LabelRowMetadataIncludeArgs,
)
from encord_agents.core.dependencies.models import Context
from encord_agents.core.dependencies.utils import get_dependant, solve_dependencies
from encord_agents.core.exceptions import EncordEditorAgentException
from encord_agents.core.run_token import (
    AgentRunTokenMode,
    AgentRunTokenSettings,
    check_agent_run_token,
    forwarding_agent_run_token,
)
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
    agent_run_token_mode: AgentRunTokenMode | None = None,
    agent_run_token_audiences: Sequence[str] | None = None,
    agent_run_token_organisations: Sequence[str] | None = None,
) -> Callable[[AgentFunction], Callable[[Request], Response]]:
    r"""
    Wrapper to make resources available for gcp editor agents.

    The editor agents are intended to be used using dependency injections.
    You can learn more via out [documentation](https://docs.encord.com/platform-documentation/).

    Args:
        label_row_metadata_include_args: arguments to overwrite default arguments
            on `project.list_label_rows_v2()`.
        label_row_initialise_labels_args: Arguments to overwrite default arguments
            on `label_row.initialise_labels(...)`
        custom_cors_regex: A regex to use for the CORS settings. Defaults to the production Encord apps,
            `https://app.encord.com` and `https://app.us.encord.com`, only. The regex replaces the default,
            so to also allow another frontend, match every origin you trust, e.g.,
            `r"^https:\/\/(?:app\.(?:us\.)?encord\.com|my-frontend\.example\.com)$"`.
        agent_run_token_mode: Whether to check the agent run token Encord sends with each call:
            `off`, `warn` (log only) or `enforce` (refuse calls without a valid token). Overrides
            `ENCORD_AGENT_RUN_TOKEN_MODE`, which defaults to `off`. See `encord_agents.core.run_token`.
        agent_run_token_audiences: The addresses this agent is registered under in Encord, checked
            against the token's audience. Overrides `ENCORD_AGENT_RUN_TOKEN_AUDIENCES`.
            Required in `enforce` mode.
        agent_run_token_organisations: The Encord organisation UUIDs this agent serves. When set,
            tokens for other organisations do not verify. Overrides `ENCORD_AGENT_RUN_TOKEN_ORGANISATIONS`.

    Returns:
        A wrapped function suitable for gcp functions.
    """

    def context_wrapper_inner(func: AgentFunction) -> Callable[[Request], Response]:
        dependant = get_dependant(func=func)
        cors_regex = re.compile(custom_cors_regex or ENCORD_DOMAIN_REGEX)

        run_token_settings = AgentRunTokenSettings.resolve(
            agent_run_token_mode, agent_run_token_audiences, agent_run_token_organisations
        )

        def handle(request: Request) -> Response:
            if request.method == "OPTIONS":
                response = make_response("")
                response.headers["Vary"] = "Origin"

                if not cors_regex.fullmatch(request.origin):
                    response.status_code = HTTPStatus.FORBIDDEN
                    return response

                headers = {
                    "Access-Control-Allow-Origin": request.origin,
                    "Access-Control-Allow-Methods": "POST",
                    "Access-Control-Allow-Headers": (
                        f"Content-Type, {EDITOR_TEST_REQUEST_HEADER}, {HEADER_CLOUD_TRACE_CONTEXT}, "
                        f"{AGENT_RUN_TOKEN_HEADER}"
                    ),
                    "Access-Control-Max-Age": "3600",
                }
                response.headers.update(headers)
                response.status_code = HTTPStatus.NO_CONTENT
                return response

            if request.headers.get(EDITOR_TEST_REQUEST_HEADER):
                logging.info("Editor test request")
                return _generate_response()
            trace_id: str | None = None
            if x_cloud_trace_context := request.headers.get(HEADER_CLOUD_TRACE_CONTEXT):
                trace_id = x_cloud_trace_context.split("/")[0]
                logging.info(f"Trace id: {trace_id}")
            if not request.is_json:
                raise Exception("Request should be JSON. Migrated over to new format")
            frame_data = FrameData.model_validate(request.get_json())
            logging.info(f"Request: {frame_data}")

            client = get_user_client(trace_id=trace_id)
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
                except Exception as exc:
                    logging.exception(f"Exception when executing agent function: {frame_data=}", exc_info=exc)
                    response = _generate_response(
                        to_jsonable_python({"message": f"Internal server error: {str(exc)}"}),
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                    return response
            return _generate_response()

        @wraps(func)
        def wrapper(request: Request) -> Response:
            if (
                run_token_settings.mode is AgentRunTokenMode.OFF
                or request.method == "OPTIONS"
                or request.headers.get(EDITOR_TEST_REQUEST_HEADER)
                or not request.is_json
            ):
                return handle(request)
            try:
                frame_data = FrameData.model_validate(request.get_json())
            except ValidationError:
                return handle(request)

            check = check_agent_run_token(request.headers.get(AGENT_RUN_TOKEN_HEADER), frame_data, run_token_settings)
            if check.refused:
                return _generate_response(
                    to_jsonable_python({"message": "A valid Encord agent run token is required."}),
                    HTTPStatus.UNAUTHORIZED,
                )
            with forwarding_agent_run_token(check):
                return handle(request)

        return wrapper

    return context_wrapper_inner

import logging
from contextlib import ExitStack
from functools import wraps
from http import HTTPStatus
from typing import Any, Callable, Dict, cast

from encord.exceptions import AuthorisationError
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.storage import StorageItem
from pydantic import ValidationError
from pydantic_core import to_jsonable_python

from encord_agents import FrameData
from encord_agents.core.constants import EDITOR_TEST_REQUEST_HEADER
from encord_agents.core.data_model import EditorAgentResponse, LabelRowInitialiseLabelsArgs, LabelRowMetadataIncludeArgs
from encord_agents.core.dependencies.models import Context
from encord_agents.core.dependencies.utils import get_dependant, solve_dependencies
from encord_agents.core.exceptions import EncordEditorAgentException
from encord_agents.core.utils import get_user_client

AgentFunction = Callable[..., Any]


def _generate_response(body: dict[str, Any] | None = None, status_code: int | None = None) -> Dict[str, Any]:
    """
    Generate a Lambda response dictionary with a 200 status code.
    """
    has_body = bool(body)
    return {
        "statusCode": status_code or (200 if has_body else 204),
        "body": to_jsonable_python(body) if has_body else "",  # Lambda expects a string body, even if empty
        # "headers": CORS headers are handled by AWS Lambda from the configurations.
    }


def editor_agent(
    *,
    label_row_metadata_include_args: LabelRowMetadataIncludeArgs | None = None,
    label_row_initialise_labels_args: LabelRowInitialiseLabelsArgs | None = None,
) -> Callable[[AgentFunction], Callable[[Dict[str, Any], Any], Dict[str, Any]]]:
    """
    Wrapper to make resources available for AWS Lambda editor agents.
    """

    def context_wrapper_inner(func: AgentFunction) -> Callable[[Dict[str, Any], Any], Dict[str, Any]]:
        dependant = get_dependant(func=func)

        @wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            headers = event.get("headers", {})
            if headers.get(EDITOR_TEST_REQUEST_HEADER) or headers.get(EDITOR_TEST_REQUEST_HEADER.lower()):
                logging.info("Editor test request")
                return _generate_response()

            try:
                body = event.get("body")
                frame_data: FrameData | None = None
                if not body:
                    return {"statusCode": 400, "body": {"errors": ["No request body"], "message": "No request body"}}
                if isinstance(body, str):
                    logging.info("Parsing body as string json")
                    frame_data = FrameData.model_validate_json(body)
                elif isinstance(body, dict):
                    logging.info("Parsing body as json object")
                    frame_data = FrameData.model_validate(body)
                logging.info(f"Request: {frame_data}")
            except ValidationError as err:
                logging.error(f"Error parsing request: {err}")
                return {
                    "statusCode": 400,
                    "body": {
                        "errors": err.errors(),
                        "message": ", ".join([e["msg"] for e in err.errors()]),
                    },
                }
            frame_data = cast(FrameData, frame_data)

            client = get_user_client()
            try:
                project = client.get_project(frame_data.project_hash)
            except AuthorisationError:
                return {"statusCode": 403, "body": "Forbidden"}

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
                except AuthorisationError:
                    return {"statusCode": 403, "body": "Forbidden"}

            context_obj = Context(
                project=project, label_row=label_row, frame_data=frame_data, storage_item=storage_item
            )
            result: None | Any | EditorAgentResponse = None
            with ExitStack() as stack:
                try:
                    dependencies = solve_dependencies(context=context_obj, dependant=dependant, stack=stack)
                except AuthorisationError:
                    return {"statusCode": 403, "body": "Forbidden"}
                try:
                    result = func(**dependencies.values)
                    if isinstance(result, EditorAgentResponse):
                        return _generate_response(result.model_dump())
                    return _generate_response()
                except EncordEditorAgentException as exc:
                    return _generate_response(
                        exc.json_response_body,
                        status_code=HTTPStatus.BAD_REQUEST,
                    )

        return wrapper

    return context_wrapper_inner

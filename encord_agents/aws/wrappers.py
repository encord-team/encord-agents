import logging
import re
from contextlib import ExitStack
from functools import wraps
from typing import Any, Callable, Dict

from encord.exceptions import AuthorisationError
from encord.objects.ontology_labels_impl import LabelRowV2
from encord.storage import StorageItem
from pydantic import ValidationError
from pydantic_core import to_jsonable_python

from encord_agents import FrameData
from encord_agents.core.constants import EDITOR_TEST_REQUEST_HEADER, ENCORD_DOMAIN_REGEX
from encord_agents.core.data_model import LabelRowInitialiseLabelsArgs, LabelRowMetadataIncludeArgs
from encord_agents.core.dependencies.models import Context
from encord_agents.core.dependencies.utils import get_dependant, solve_dependencies
from encord_agents.core.utils import get_user_client

AgentFunction = Callable[..., Any]


def generate_response() -> Dict[str, Any]:
    """
    Generate a Lambda response dictionary with a 200 status code.
    """
    return {
        "statusCode": 204,
        "body": "",  # Lambda expects a string body, even if empty
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
                return generate_response()

            try:
                body = event.get("body")
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
                    label_row = project.list_label_rows_v2(data_hashes=[frame_data.data_hash])[0]
                assert label_row.backing_item_uuid, "This is a server response so guaranteed to have this"
                storage_item = client.get_storage_item(label_row.backing_item_uuid)

            context_obj = Context(
                project=project, label_row=label_row, frame_data=frame_data, storage_item=storage_item
            )
            with ExitStack() as stack:
                dependencies = solve_dependencies(context=context_obj, dependant=dependant, stack=stack)
                func(**dependencies.values)
            return generate_response()

        return wrapper

    return context_wrapper_inner

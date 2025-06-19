"""
Convenience method to easily extend FastAPI servers
with the appropriate CORS Middleware to allow
interactions from the Encord platform.
"""

import typing
from http import HTTPStatus

from encord.exceptions import AuthorisationError

from encord_agents.core.exceptions import EncordEditorAgentException

try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, Response
    from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
    from starlette.types import ASGIApp
except ModuleNotFoundError:
    print(
        'To use the `fastapi` dependencies, you must also install fastapi. `python -m pip install "fastapi[standard]"'
    )
    exit()

from encord_agents.core.constants import EDITOR_TEST_REQUEST_HEADER, ENCORD_DOMAIN_REGEX


# Type checking does not work here because we do not enforce people to
# install fastapi as they can use package for, e.g., task runner wo fastapi.
class EncordCORSMiddleware(CORSMiddleware):  # type: ignore [misc, unused-ignore]
    """
    Like a regular `fastapi.middleware.cors.CORSMiddleware` but matches against
    the Encord origin by default and handles X-Encord-Editor-Agent test header

    **Example:**
    ```python
    from fastapi import FastAPI
    from encord_agents.fastapi.cors import EncordCORSMiddleware

    app = FastAPI()
    app.add_middleware(EncordCORSMiddleware)
    ```

    The CORS middleware allows POST requests from the Encord domain.
    """

    def __init__(
        self,
        app: ASGIApp,
        allow_origins: typing.Sequence[str] = (),
        allow_methods: typing.Sequence[str] = ("POST",),
        allow_headers: typing.Sequence[str] = (EDITOR_TEST_REQUEST_HEADER,),
        allow_credentials: bool = False,
        allow_origin_regex: str = ENCORD_DOMAIN_REGEX,
        expose_headers: typing.Sequence[str] = (),
        max_age: int = 3600,
    ) -> None:
        super().__init__(
            app,
            allow_origins,
            allow_methods,
            allow_headers,
            allow_credentials,
            allow_origin_regex,
            expose_headers,
            max_age,
        )


class EncordTestHeaderMiddleware(BaseHTTPMiddleware):  # type: ignore [misc, unused-ignore]
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Middleware to handle the X-Encord-Editor-Agent test header.

        Args:
            request (Request):
            call_next (RequestResponseEndpoint):

        Returns:
            Response
        """
        if request.method == "POST":
            if request.headers.get(EDITOR_TEST_REQUEST_HEADER):
                return JSONResponse(content=None, status_code=200)

        return await call_next(request)


async def _encord_editor_agent_exception_handler(request: Request, exc: EncordEditorAgentException) -> JSONResponse:
    """
    Custom exception handler for encord_agents.core.exceptions.EncordEditorAgentException.

    Args:
        request: FastAPI request object
        exc: Exception raised by the agent implementation

    Returns:
        JSON response with the error message and status code 400
    """
    return JSONResponse(
        status_code=HTTPStatus.BAD_REQUEST,
        content=exc.json_response_body,
    )


async def _authorization_error_exception_handler(request: Request, exc: AuthorisationError) -> JSONResponse:
    """
    Custom exception handler for encord.exceptions.AuthorisationError.

    Args:
        request: FastAPI request object
        exc: Exception raised by the Encord platform

    Returns:
        JSON response with the error message and status code 403
    """
    return JSONResponse(
        status_code=HTTPStatus.FORBIDDEN,
        content={"message": exc.message},
    )


def get_encord_app(*, custom_cors_regex: str | None = None) -> FastAPI:
    """
    Get a FastAPI app with the Encord middleware.

    Args:
        custom_cors_regex (str | None, optional): A regex to use for the CORS middleware.
            Only necessary if you are not using the default Encord domain.

    Returns:
        FastAPI: A FastAPI app with the Encord middleware.
    """
    app = FastAPI()
    app.add_middleware(
        EncordCORSMiddleware,
        allow_origin_regex=custom_cors_regex or ENCORD_DOMAIN_REGEX,
    )
    app.add_middleware(EncordTestHeaderMiddleware)
    app.exception_handlers[AuthorisationError] = _authorization_error_exception_handler
    app.exception_handlers[EncordEditorAgentException] = _encord_editor_agent_exception_handler
    return app

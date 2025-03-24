"""
Convenience method to easily extend FastAPI servers
with the appropriate CORS Middleware to allow
interactions from the Encord platform.
"""

import json
import typing
from http import HTTPStatus

from encord.exceptions import AuthorisationError

try:
    from fastapi import Request
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
class _EncordCORSMiddlewarePure(CORSMiddleware):  # type: ignore [misc, unused-ignore]
    def __init__(
        self,
        app: ASGIApp,
        allow_origins: typing.Sequence[str] = (),
        allow_methods: typing.Sequence[str] = ("POST",),
        allow_headers: typing.Sequence[str] = (),
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


class EncordCORSMiddleware(BaseHTTPMiddleware, _EncordCORSMiddlewarePure):  # type: ignore [misc, unused-ignore]
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

    The CORS middleware will allow POST requests from the Encord domain.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "POST":
            if request.headers.get(EDITOR_TEST_REQUEST_HEADER):
                return JSONResponse(content=None, status_code=200)

        return await call_next(request)


async def authorization_error_exception_handler(request: Request, exc: AuthorisationError) -> JSONResponse:
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

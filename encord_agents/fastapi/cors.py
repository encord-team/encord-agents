"""
Convenience method to easily extend FastAPI servers
with the appropriate CORS Middleware to allow
interactions from the Encord platform.
"""

import asyncio
import json
import typing
from http import HTTPStatus
from uuid import UUID

from encord.exceptions import AuthorisationError
from pydantic import ValidationError

from encord_agents.core.data_model import FrameData

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

    The CORS middleware will allow POST requests from the Encord domain.
    """

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


class FieldPairLockMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
    ):
        super().__init__(app)
        self.field_locks: dict[tuple[UUID, UUID], asyncio.Lock] = {}
        self.locks_lock = asyncio.Lock()

    async def get_lock(self, frame_data: FrameData) -> asyncio.Lock:
        lock_key = (frame_data.project_hash, frame_data.data_hash)
        async with self.locks_lock:
            if lock_key not in self.field_locks:
                self.field_locks[lock_key] = asyncio.Lock()
            return self.field_locks[lock_key]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method != "POST":
            return await call_next(request)
        try:
            body = await request.body()
            try:
                frame_data = FrameData.model_validate_json(body)
            except ValidationError:
                # Hope that route doesn't use FrameData
                return await call_next(request)
            lock = await self.get_lock(frame_data)
            async with lock:
                # Create a new request with the same body since we've already consumed it
                request._body = body
                return await call_next(request)
        except Exception as e:
            return Response(
                content=json.dumps({"detail": f"Error in middleware: {str(e)}"}),
                status_code=500,
                media_type="application/json",
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
    app.add_middleware(FieldPairLockMiddleware)
    app.exception_handlers[AuthorisationError] = _authorization_error_exception_handler
    return app

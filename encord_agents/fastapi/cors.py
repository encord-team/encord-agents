"""
Convenience method to easily extend FastAPI servers
with the appropriate CORS Middleware to allow
interactions from the Encord platform.
"""

import json
import typing

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

from encord_agents.core.constants import ENCORD_DOMAIN_REGEX

TEST_REQUEST_PAYLOAD: dict[str, str | int] = {
    "projectHash": "027e0c65-c53f-426d-9f02-04fafe8bd80e",
    "dataHash": "038ed92d-dbe8-4991-a3aa-6ede35d6e62d",
    "frame": 10,
}


# Type checking does not work here because we do not enforce people to
# install fastapi as they can use package for, e.g., task runner wo fastapi.
class EncordCORSMiddlewarePure(CORSMiddleware):  # type: ignore [misc, unused-ignore]
    """
    Like a regular `fastapi.midleware.cors.CORSMiddleware` but matches against
    the Encord origin by default.

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


class EncordCORSMiddleware(BaseHTTPMiddleware, EncordCORSMiddlewarePure):  # type: ignore [misc, unused-ignore]
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "POST":
            body_bytes = await request.body()

            if not body_bytes:
                return await call_next(request)
            try:
                payload = json.loads(body_bytes)

                if payload == TEST_REQUEST_PAYLOAD:
                    return JSONResponse(
                        content=None,
                        status_code=200,
                    )

            except json.JSONDecodeError:
                pass

        return await call_next(request)

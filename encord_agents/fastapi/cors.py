"""
Convenience method to easily extend FastAPI servers
with the appropriate CORS Middleware to allow
interactions from the Encord platform.
"""

import typing

try:
    from fastapi.middleware.cors import CORSMiddleware
    from starlette.types import ASGIApp
except ModuleNotFoundError:
    print(
        'To use the `fastapi` dependencies, you must also install fastapi. `python -m pip install "fastapi[standard]"'
    )
    exit()

ENCORD_DOMAIN_REGEX = (
    r"^https:\/\/(?:(?:cord-ai-development--[\w\d]+-[\w\d]+\.web.app)|(?:(?:dev|staging|app)\.encord\.com))$"
)


class EncordCORSMiddleware(CORSMiddleware):
    """
    Like a regular `fastapi.midleware.cors.CORSMiddleware` but matches against
    the encord origin by default.

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